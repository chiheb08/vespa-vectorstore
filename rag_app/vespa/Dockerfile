FROM vespaengine/vespa:latest

# Copy the Vespa application package into the image.
COPY app /app
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]


