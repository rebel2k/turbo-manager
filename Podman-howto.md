# Podman/Kind on MacOS
## Install Podman

1. `brew install podman-desktop`
2. `brew install podman-compose`
3. `podman machine init`
4. `podman machine start` (in case you need that and have an error, check workaround 3 on [https://github.com/Homebrew/homebrew-core/issues/140244])
5. `podman run --name turbo-manager -p 8080:80 turbo-manager`
6. (optional) Add an alias in your config (~/.zshrc or ~./bashrc) for using podman or docker commands as you prefer: `alias docker="podman"`

## Install Kind

1. `brew install kind`
2. (optional) Change your config (~/.zshrc or ~./bashrc) so kind is using podman as container provider: `export KIND_EXPERIMENTAL_PROVIDER=podman`
3. `kind create cluster`

## Build the image
`podman build . -t turbo-manager`

## Run the image
`podman run -p 8080:80 -d turbo-manager`