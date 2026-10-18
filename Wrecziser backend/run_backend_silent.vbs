Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

pythonExe = strDir & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonExe) Then
    pythonExe = strDir & "\.venv\Scripts\python.exe"
End If
If Not fso.FileExists(pythonExe) Then
    pythonExe = "pythonw.exe"
End If

mainPy = strDir & "\main.py"
WshShell.Run chr(34) & pythonExe & chr(34) & " " & chr(34) & mainPy & chr(34), 0, False
