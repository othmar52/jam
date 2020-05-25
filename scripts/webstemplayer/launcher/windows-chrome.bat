

rem  to be able to access audioContext under file:/// protocol
rem  we have to add certain arguments to browsers start

rem  TODO: test paths with whitespaces & special chars

set launchCmd=chrome.exe
set launchCmd=%launchCmd% --disable-web-security
set launchCmd=%launchCmd% --disable-features=TranslateUI
set launchCmd=%launchCmd% --user-data-dir="%~dp0browser-temp-dir\win"
set launchCmd=%launchCmd% --app="file:///%~dp0..\index.htm#forceMeter"

start %launchCmd%
