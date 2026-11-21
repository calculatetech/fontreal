# Load the matching Fontreal providers during Plasma login.
if [ -z "${LD_PRELOAD:-}" ]; then
    export QT_PLUGIN_PATH="/usr/lib/fontreal/qt6/plugins${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
    export QT_QPA_GENERIC_PLUGINS="${QT_QPA_GENERIC_PLUGINS:+$QT_QPA_GENERIC_PLUGINS,}fontreal-cached-probe,fontreal-quick-default-probe"
    export FONTREAL_QUAL_TONE=1
fi
