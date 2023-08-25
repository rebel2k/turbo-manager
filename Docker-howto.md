# How To build a local Container:
1. Checkout this Repo
2. Build the image: `docker build . -t turbo-manager`
3. Run the created image and map Port 80 of the Container to Port 8080 on your Localhost: `docker run -p 8080:80 -d turbo-manager`
4. Go to [localhost:8080]](http://localhost:8080), Voilá 