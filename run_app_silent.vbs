' run_app_silent.vbs (no venv)
Option Explicit
Dim shell, cmd, workDir
Set shell = CreateObject("WScript.Shell")

workDir = "C:\Users\Ian D N\Desktop\Unit_PropertyCard_App"
cmd = "cmd /c cd /d """ & workDir & """ && py -m streamlit run app.py --server.port 8501 --server.headless true"

shell.Run cmd, 0, False
WScript.Sleep 2500
shell.Run "http://localhost:8501", 1, False
