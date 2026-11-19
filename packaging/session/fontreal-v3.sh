# Plasma imports these values when it starts the session.
export FONTREAL_RENDERING=0
export FONTREAL_BLEND=
export FONTREAL_CONTRAST=
export FONTREAL_FITTING=
# An empty value also clears a V2 preset retained by the user service manager.
export FONTREAL_PROFILE=

if [ -f "${XDG_CONFIG_HOME:-"$HOME/.config"}/fontreal/enabled" ] &&
    dpkg-query -W -f='${Package}\t${Version}\n' libqt6gui6:amd64 libqt6quick6:amd64 2>/dev/null |
        cmp -s - /usr/share/fontreal/runtime-versions; then
    export FONTREAL_RENDERING=3
fi
