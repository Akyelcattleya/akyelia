' =============================================
' Akyel AI - Installer au demarrage de Windows
' Fais un double-clic pour ajouter Akyel AI
' au demarrage automatique de Windows
' =============================================
Dim WshShell, StartupPath, ShortcutPath, ScriptPath

Set WshShell = CreateObject("WScript.Shell")

' Chemin du dossier Demarrage Windows
StartupPath = WshShell.SpecialFolders("Startup")

' Chemin vers le script batch
ScriptPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\start_all.bat"

' Creer le raccourci
ShortcutPath = StartupPath & "\Akyel AI.lnk"
Dim Shortcut
Set Shortcut = WshShell.CreateShortcut(ShortcutPath)

With Shortcut
    .TargetPath = ScriptPath
    .WindowStyle = 7       ' Minimisee
    .Description = "Akyel AI - Smart Multi-LLM Assistant"
    .WorkingDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
End With

Shortcut.Save

' Confirmation
MsgBox "✅ Akyel AI a ete installe au demarrage de Windows !" & vbCrLf & vbCrLf & _
       "A chaque demarrage de Windows, OmniRoute et Akyel AI" & vbCrLf & _
       "se lanceront automatiquement en arriere-plan." & vbCrLf & vbCrLf & _
       "📍 Raccourci : " & ShortcutPath, _
       vbInformation, "Akyel AI - Demarrage automatique"
