export XDG_RUNTIME_DIR="/run/user/$UID"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm if it exists
[ -s "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"  # This loads the cargo environment if it exists
export PATH=$PATH:$HOME/.local/bin

