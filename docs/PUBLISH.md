# Publishing this project

From an extracted folder:

```bash
# Local identity/configuration are your normal Git settings.
git init -b main
git add .
git commit -m "Implement LLVM affine loop strength-reduction pass"

# Requires GitHub CLI installed and `gh auth login` completed.
gh repo create strideforge-llvm --public --source=. --remote=origin --push
```

Alternatively, create an empty repository named `strideforge-llvm` on GitHub, then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/strideforge-llvm.git
git push -u origin main
```

After pushing: open **Actions → LLVM 18 validation** and check that the full compiler build, IR verifier and differential tests have succeeded. If the workflow fails, fix the repository before sharing it on a resume. Then run the benchmark on your own machine and commit actual measured results (or omit performance claims). Read [INTEL_APPLICATION.md](INTEL_APPLICATION.md) for accurate resume wording.
