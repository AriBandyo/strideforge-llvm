; All three cases are intentionally outside the pass's legality envelope.
source_filename = "negative.ll"

define i64 @dynamic_stride(i64 %start, i64 %step, i64 %count) {
entry:
  br label %header
header:
  %iv = phi i64 [ %start, %entry ], [ %iv.next, %latch ]
  %k = phi i64 [ 0, %entry ], [ %k.next, %latch ]
  %scaled = mul i64 %iv, 37
  br label %latch
latch:
  %iv.next = add i64 %iv, %step
  %k.next = add i64 %k, 1
  %done = icmp eq i64 %k.next, %count
  br i1 %done, label %exit, label %header
exit:
  ret i64 %scaled
}

define i64 @dynamic_factor(i64 %start, i64 %factor, i64 %count) {
entry:
  br label %header
header:
  %iv = phi i64 [ %start, %entry ], [ %iv.next, %latch ]
  %k = phi i64 [ 0, %entry ], [ %k.next, %latch ]
  %scaled = mul i64 %iv, %factor
  br label %latch
latch:
  %iv.next = add i64 %iv, 1
  %k.next = add i64 %k, 1
  %done = icmp eq i64 %k.next, %count
  br i1 %done, label %exit, label %header
exit:
  ret i64 %scaled
}

define i64 @mul_outside_header(i64 %start, i64 %count) {
entry:
  br label %header
header:
  %iv = phi i64 [ %start, %entry ], [ %iv.next, %latch ]
  %k = phi i64 [ 0, %entry ], [ %k.next, %latch ]
  br label %body
body:
  %scaled = mul i64 %iv, 37
  br label %latch
latch:
  %iv.next = add i64 %iv, 1
  %k.next = add i64 %k, 1
  %done = icmp eq i64 %k.next, %count
  br i1 %done, label %exit, label %header
exit:
  ret i64 %scaled
}
