# to be able to access audioContext under file:/// protocol
# we have to add certain arguments to browsers start

# TODO: test paths with whitespaces & special chars

scriptPath="$( cd "$(dirname "$0")" ; pwd -P )"

launchCmd=(--disable-web-security)
launchCmd+=(--disable-features=TranslateUI)
launchCmd+=(--user-data-dir="$scriptPath/browser-temp-dir/osx")
launchCmd+=(--app="file:///$scriptPath/../index.htm#forceMeter")
open -n -a /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --args "${launchCmd[@]}"
