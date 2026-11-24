$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$s = $ws.CreateShortcut("$desktop\RoboSats Coordinator.lnk")
$s.TargetPath = "c:\Users\Garrysan\Documents\robosats\start_coordinator.bat"
$s.WorkingDirectory = "c:\Users\Garrysan\Documents\robosats"
$s.Description = "RoboSats P2P Coordinator Command Center"
$s.IconLocation = "shell32.dll, 220"
$s.Save()

# Also create with Russian title
$s2 = $ws.CreateShortcut("$desktop\RoboSats Координатор.lnk")
$s2.TargetPath = "c:\Users\Garrysan\Documents\robosats\start_coordinator.bat"
$s2.WorkingDirectory = "c:\Users\Garrysan\Documents\robosats"
$s2.Description = "RoboSats P2P Coordinator Command Center"
$s2.IconLocation = "shell32.dll, 220"
$s2.Save()

Write-Host "SHORTCUT_CREATED"
