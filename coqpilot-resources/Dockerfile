FROM python:3.11-slim AS base

# Install system packages we need, including libgmp-dev and pkg-config
RUN apt-get update && apt-get install -y --no-install-recommends \
    opam \
    m4 \
    build-essential \
    git \
    curl \
    ca-certificates \
    libgmp-dev \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

# Initialize opam (disable the sandbox which won't work in Docker)
RUN opam init --disable-sandboxing -y

# Switch to bash so we can do "eval $(opam env)" in one RUN layer
SHELL ["/bin/bash", "-c"]

# Create & activate an OCaml switch (e.g., 4.14.1) so we can install coq-lsp
RUN opam switch create 4.14.1 ocaml-base-compiler.4.14.1 -y && \
    opam switch set 4.14.1 && \
    eval "$(opam env)" && \
    opam install -y coq coq-lsp

ENV PATH="/root/.opam/4.14.1/bin:${PATH}"

CMD ["/bin/bash"]
