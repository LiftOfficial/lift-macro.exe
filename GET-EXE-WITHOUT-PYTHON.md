# Get the Windows EXE without installing Python

LIFT MACRO 12 includes a GitHub Actions build workflow. GitHub builds the Windows app on its own Windows runner, so **you do not install Python on your PC**.

## One-time setup
1. Sign in to GitHub or create an account.
2. Create a new repository. You can name it `lift-macro`.
3. Upload the contents of this project folder to the repository. Make sure `.github/workflows/build-windows.yml` is included. If uploading in the browser, create the `.github/workflows` folders and add `build-windows.yml` there.
4. Open the repository's **Actions** tab.
5. Select **Build LIFT MACRO for Windows**.
6. Choose **Run workflow**, then run it.
7. Wait for the workflow to finish successfully.
8. Open the completed run and find **Artifacts** at the bottom.
9. Download **LIFT-MACRO-Windows** and extract the ZIP.
10. Run `LIFT-MACRO.exe` from the extracted `LIFT-MACRO` folder. Keep the other files beside it.

## Important
- Python is installed only on GitHub's temporary build machine; it is not required on your computer.
- This workflow produces a portable Windows folder packaged as a ZIP, not a single-file installer.
- The ZIP contains the EXE and its required runtime files. Do not move the EXE out of its folder.
- Windows may show its normal first-run security prompt because the app is not code-signed.
- The local `build_exe.bat` remains available if you prefer to build on your own PC; that local route requires Python.
- This workflow has been added to the project, but a Windows build must still run in GitHub Actions before the resulting EXE can be verified.
