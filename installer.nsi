!define APP_NAME "TAC Writer"
!define APP_VERSION "1.28.1"
!define APP_EXE "TacWriter.exe"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "TacWriter-Setup-${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES\TacWriter"

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "dist\TacWriter\*.*"
    
    ; Criar atalho
    CreateShortCut "$DESKTOP\TAC Writer.lnk" "$INSTDIR\${APP_EXE}"
    CreateDirectory "$SMPROGRAMS\TAC Writer"
    CreateShortCut "$SMPROGRAMS\TAC Writer\TAC Writer.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortCut "$SMPROGRAMS\TAC Writer\Desinstalar.lnk" "$INSTDIR\uninstall.exe"
    
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
    RMDir /r "$INSTDIR"
    Delete "$DESKTOP\TAC Writer.lnk"
    RMDir /r "$SMPROGRAMS\TAC Writer"
SectionEnd