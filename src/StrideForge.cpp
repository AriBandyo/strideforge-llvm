// SPDX-License-Identifier: MIT
// StrideForge: a conservative, out-of-tree LLVM New Pass Manager plugin.
//
// For a loop-carried integer induction variable i with recurrence
//      i_next = i + step,
// transform a multiply s = i * C in the loop header to a second induction
// variable s_next = s + step*C, seeded with s0 = i0*C in the preheader.
//
// All arithmetic is performed at the source integer bitwidth. The identity
// is valid modulo 2^N, including unsigned wraparound; no fast-math or
// no-signed-wrap assumptions are introduced.

#include "llvm/ADT/APInt.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/raw_ostream.h"

using namespace llvm;

namespace {
struct Candidate {
  BinaryOperator *Mul;
  PHINode *IV;
  ConstantInt *Factor;
  APInt Step;
};

// Only affine, integer, single-latch loops in a readily auditable shape.
// Do not speculate arbitrary instructions or touch CFG/aliasing relationships.
static bool getStep(PHINode *IV, BasicBlock *Preheader,
                    BasicBlock *Latch, APInt &Step) {
  if (IV->getNumIncomingValues() != 2 ||
      IV->getBasicBlockIndex(Preheader) < 0 ||
      IV->getBasicBlockIndex(Latch) < 0)
    return false;

  auto *Update = dyn_cast<BinaryOperator>(
      IV->getIncomingValueForBlock(Latch));
  if (!Update || Update->getParent() != Latch)
    return false;

  auto *C0 = dyn_cast<ConstantInt>(Update->getOperand(0));
  auto *C1 = dyn_cast<ConstantInt>(Update->getOperand(1));
  if (Update->getOpcode() == Instruction::Add) {
    if (Update->getOperand(0) == IV && C1)
      Step = C1->getValue();
    else if (Update->getOperand(1) == IV && C0)
      Step = C0->getValue();
    else
      return false;
  } else if (Update->getOpcode() == Instruction::Sub &&
             Update->getOperand(0) == IV && C1) {
    Step = -C1->getValue();
  } else {
    return false;
  }
  return !Step.isZero();
}

static void collectCandidates(Loop *L, SmallVectorImpl<Candidate> &Out) {
  BasicBlock *Header = L->getHeader();
  BasicBlock *Preheader = L->getLoopPreheader();
  BasicBlock *Latch = L->getLoopLatch();
  if (!Preheader || !Latch || Header == Latch ||
      L->getNumBackEdges() != 1)
    return;
  auto *PreBr = dyn_cast<BranchInst>(Preheader->getTerminator());
  if (!PreBr || !PreBr->isUnconditional() ||
      PreBr->getSuccessor(0) != Header)
    return;

  for (Instruction &I : *Header) {
    auto *Mul = dyn_cast<BinaryOperator>(&I);
    if (!Mul || Mul->getOpcode() != Instruction::Mul)
      continue;

    PHINode *IV = nullptr;
    ConstantInt *Factor = nullptr;
    if ((IV = dyn_cast<PHINode>(Mul->getOperand(0))) &&
        (Factor = dyn_cast<ConstantInt>(Mul->getOperand(1)))) {
      // matched
    } else if ((IV = dyn_cast<PHINode>(Mul->getOperand(1))) &&
               (Factor = dyn_cast<ConstantInt>(Mul->getOperand(0)))) {
      // commuted multiply
    } else {
      continue;
    }

    if (IV->getParent() != Header ||
        !IV->getType()->isIntegerTy() ||
        !(IV->getType()->getIntegerBitWidth() == 32 ||
          IV->getType()->getIntegerBitWidth() == 64) ||
        Factor->isZero() || Factor->isOne())
      continue;

    APInt Step(IV->getType()->getIntegerBitWidth(), 0);
    if (!getStep(IV, Preheader, Latch, Step))
      continue;

    Out.push_back({Mul, IV, Factor, Step});
  }
}

static void gatherLoops(Loop *L, SmallVectorImpl<Loop *> &All) {
  // Inner loops first so rewriting never invalidates analysis of children.
  for (Loop *Child : L->getSubLoops())
    gatherLoops(Child, All);
  All.push_back(L);
}

class AffineStrengthReducePass
    : public PassInfoMixin<AffineStrengthReducePass> {
public:
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM) {
    LoopInfo &LI = FAM.getResult<LoopAnalysis>(F);
    SmallVector<Loop *, 8> All;
    for (Loop *L : LI)
      gatherLoops(L, All);

    bool Changed = false;
    for (Loop *L : All) {
      SmallVector<Candidate, 8> Candidates;
      collectCandidates(L, Candidates);
      BasicBlock *Header = L->getHeader();
      BasicBlock *Preheader = L->getLoopPreheader();
      BasicBlock *Latch = L->getLoopLatch();
      for (const Candidate &C : Candidates) {
        // The preheader dominates every iteration of the loop.
        IRBuilder<> InitBuilder(Preheader->getTerminator());
        Value *Init = InitBuilder.CreateMul(
            C.IV->getIncomingValueForBlock(Preheader), C.Factor,
            "sf.init");

        // PHI nodes must precede all non-PHI instructions in the header.
        PHINode *Scaled = PHINode::Create(
            C.IV->getType(), 2, "sf.scaled", &*Header->begin());
        Scaled->addIncoming(Init, Preheader);

        APInt Delta = C.Step * C.Factor->getValue();
        IRBuilder<> NextBuilder(Latch->getTerminator());
        Value *Next = NextBuilder.CreateAdd(
            Scaled, ConstantInt::get(C.IV->getType(), Delta), "sf.next");
        Scaled->addIncoming(Next, Latch);

        C.Mul->replaceAllUsesWith(Scaled);
        C.Mul->eraseFromParent();
        Changed = true;
      }
    }
    // Changed instructions can invalidate scalar-evolution and similar
    // analyses. Be conservative even though the CFG itself is untouched.
    return Changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }
};

class AffineReportPass : public PassInfoMixin<AffineReportPass> {
public:
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM) {
    LoopInfo &LI = FAM.getResult<LoopAnalysis>(F);
    SmallVector<Loop *, 8> All;
    for (Loop *L : LI)
      gatherLoops(L, All);

    unsigned Eligible = 0;
    for (Loop *L : All) {
      SmallVector<Candidate, 8> Candidates;
      collectCandidates(L, Candidates);
      Eligible += Candidates.size();
    }
    errs() << "[strideforge] function=" << F.getName()
           << " loops=" << All.size()
           << " eligible_mul=" << Eligible << "\n";
    return PreservedAnalyses::all();
  }
};
} // namespace

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "StrideForge", "0.1.0",
          [](PassBuilder &PB) {
            PB.registerPipelineParsingCallback(
                [](StringRef Name, FunctionPassManager &FPM,
                   ArrayRef<PassBuilder::PipelineElement>) {
                  if (Name == "strideforge") {
                    FPM.addPass(AffineStrengthReducePass());
                    return true;
                  }
                  if (Name == "strideforge-report") {
                    FPM.addPass(AffineReportPass());
                    return true;
                  }
                  return false;
                });
          }};
}
