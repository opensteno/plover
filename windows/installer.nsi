;--------------------------------
;Include Modern UI

!define MULTIUSER_MUI
!define MULTIUSER_USE_PROGRAMFILES64
!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_KEY "Software\Plover\${version}"
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_VALUENAME ""
!define MULTIUSER_INSTALLMODE_INSTDIR "Open Steno Project\Plover ${version}"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_KEY "Software\Plover\${version}"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_VALUENAME ""
!include MultiUser.nsh
!include MUI2.nsh

;--------------------------------
;General

  ;Name and file
  Name "Plover"

;--------------------------------
;Variables

  Var StartMenuFolder

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING
  !define MUI_WELCOMEFINISHPAGE_BITMAP "windows\installer.bmp"
  !define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH
  !define MUI_ICON "plover\assets\plover.ico"

  !define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Plover ${version}"

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_LICENSE "${srcdir}\LICENSE.txt"
  !insertmacro MULTIUSER_PAGE_INSTALLMODE
  !insertmacro MUI_PAGE_DIRECTORY

  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "SHCTX" 
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\Plover\${version}" 
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
  !insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder

  !insertmacro MUI_PAGE_INSTFILES
  
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  
;--------------------------------
;Languages
 
  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "Plover ${version}" BfWSection

  SetOutPath "$INSTDIR"

  File "${srcdir}\LICENSE.txt"
  File "${srcdir}\plover.exe"
  File "${srcdir}\plover_console.exe"
  File "${srcdir}\vcruntime140.dll"
  File /r "${srcdir}\data"
  
  ;Store installation folder
  WriteRegStr SHCTX "Software\Plover\${version}" "" "$INSTDIR"
  
  ;Add an entry in "Add/Remove Programs"
  WriteRegStr SHCTX "${UNINST_KEY}" "DisplayName" "Plover ${version}"
  WriteRegStr SHCTX "${UNINST_KEY}" "DisplayVersion" "${version}"
  WriteRegStr SHCTX "${UNINST_KEY}" "Publisher" "Open Steno Project"
  WriteRegStr SHCTX "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\data\plover.ico"
  WriteRegDWORD SHCTX "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD SHCTX "${UNINST_KEY}" "NoRepair" 1
  WriteRegDWORD SHCTX "${UNINST_KEY}" "EstimatedSize" ${install_size}
  WriteRegStr SHCTX "${UNINST_KEY}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\" /$MultiUser.InstallMode"
  WriteRegStr SHCTX "${UNINST_KEY}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /$MultiUser.InstallMode /S"

  ;Create shortcuts
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Plover ${version}.lnk" "$INSTDIR\plover.exe" "" "$INSTDIR\data\plover.ico"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Plover ${version} (debug).lnk" "$INSTDIR\plover_console.exe" "-l debug" "$INSTDIR\data\plover.ico"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Uninstall Plover ${version}.lnk" "$INSTDIR\uninstall.exe" "/$MultiUser.InstallMode"
  !insertmacro MUI_STARTMENU_WRITE_END

  ;Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

SectionEnd

;--------------------------------
;Installer Functions

  Function .onInit
    !insertmacro MULTIUSER_INIT
  FunctionEnd

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  RMDir /r "$INSTDIR\data"
  RMDir /r "$INSTDIR\hidapi-src"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\plover.exe"
  Delete "$INSTDIR\plover_console.exe"
  Delete "$INSTDIR\vcruntime140.dll"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"

  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
  Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall Plover ${version}.lnk"
  Delete "$SMPROGRAMS\$StartMenuFolder\Plover ${version}.lnk"
  Delete "$SMPROGRAMS\$StartMenuFolder\Plover ${version} (debug).lnk"
  RMDir "$SMPROGRAMS\$StartMenuFolder"
 
  DeleteRegKey SHCTX "${UNINST_KEY}"
  DeleteRegKey /ifempty SHCTX "Software\Plover\${version}"
  DeleteRegKey /ifempty SHCTX "Software\Plover"

SectionEnd

;--------------------------------
;Uninstaller Functions

  Function un.onInit
    !insertmacro MULTIUSER_UNINIT
  FunctionEnd
