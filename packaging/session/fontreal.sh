# Plasma sources this file before it starts desktop applications.
# Present inactive values overwrite an environment retained across logout.
export FONTREAL_RENDERING=0
export FONTREAL_BLEND=
export FONTREAL_CONTRAST=
export FONTREAL_FITTING=
unset FONTREAL_PROFILE

if [ -f "${XDG_CONFIG_HOME:-"$HOME/.config"}/fontreal/enabled" ] &&
    dpkg-query -W -f='${Package}\t${Version}\n' libfreetype6:amd64 libqt6gui6:amd64 libqt6quick6:amd64 2>/dev/null |
        cmp -s - /usr/share/fontreal/runtime-versions; then
    export FONTREAL_RENDERING=1
    export FONTREAL_BLEND=encoded
    export FONTREAL_CONTRAST=weighted
    export FONTREAL_FITTING=native
    export FONTREAL_PROFILE=$(/usr/bin/fontreal-session profile)
fi
