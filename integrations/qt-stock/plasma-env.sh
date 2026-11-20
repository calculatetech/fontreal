# Load the matching Fontreal providers during Plasma login.
if [ -z "${LD_PRELOAD:-}" ] &&
   [ "$(dpkg-query -W -f='${Version}' libqt6gui6:amd64 2>/dev/null)" = 6.10.2+dfsg-7 ] &&
   [ "$(dpkg-query -W -f='${Version}' libqt6quick6:amd64 2>/dev/null)" = 6.10.2+dfsg-3 ]; then
    export QT_QPA_GENERIC_PLUGINS="${QT_QPA_GENERIC_PLUGINS:+$QT_QPA_GENERIC_PLUGINS,}fontreal-cached-probe,fontreal-quick-default-probe"
    export FONTREAL_QUAL_TONE=1
fi
