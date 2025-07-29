#!/usr/bin/env bash
# scripts/rango/setup-remote-rango.sh
set -e

# Original source: https://github.com/JetBrains-Research/coqpilot/blob/cbefb3be6056504ee8e746741c693b2d2da93f81/scripts/rango/setup-remote-rango.sh

PYENV_SETUP=$(cat <<'EOF'
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
EOF
)

# Install pyenv only if it's not already installed
if ! command -v pyenv &> /dev/null; then
  echo "Installing \`pyenv\` build dependencies..."
  apt-get update && apt-get install -y \
    make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev \
    libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

  echo "Installing pyenv..."
  curl https://pyenv.run | bash

  echo "💡 Configuring \`pyenv\` to load automatically..."

  # Append to ~/.bashrc if not already present
  if ! grep -q 'export PYENV_ROOT="$HOME/.pyenv"' ~/.bashrc; then
    echo "$PYENV_SETUP" >> ~/.bashrc
  fi

  # Append to ~/.profile (used in login shells) if not already present
  if ! grep -q 'export PYENV_ROOT="$HOME/.pyenv"' ~/.profile; then
    echo "$PYENV_SETUP" >> ~/.profile
  fi

  # Source bashrc so pyenv is available in this session
  echo "Sourcing ~/.bashrc to load \`pyenv\`..."
  # shellcheck source=/dev/null
  source "$HOME/.bashrc" || true

  # Double-check that pyenv is available now
  if ! command -v pyenv &> /dev/null; then
    echo "\`pyenv\` still not available. Please reconnect your shell or run: \`source ~/.bashrc\`"
    exit 1
  fi
else
  echo "\`pyenv\` already installed"
fi

echo "Downloading \`setup-rango-repo.sh\` script"
curl -O "https://raw.githubusercontent.com/GlebSolovev/rango/imm-benchmark/setup/setup-rango-repo.sh"
chmod +x setup-rango-repo.sh

echo "Setting up Rango..."
./setup-rango-repo.sh --rango_dir "$HOME/rango" --install_local_model

echo "Setup complete!"
