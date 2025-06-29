FROM nginx:alpine

# Copy files to serve
COPY index.html /usr/share/nginx/html/
COPY style.css /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/

# Copy image folder (ensure this path is correct)
COPY assets/images/ /usr/share/nginx/html/images/


EXPOSE 80
