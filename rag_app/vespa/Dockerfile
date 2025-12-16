FROM vespaengine/vespa:latest

# Copy the Vespa application package into the image.
COPY app /app
#
# NOTE: The vespaengine/vespa image does not necessarily build as root.
# On some Docker Desktop setups, `RUN chmod` can fail with "Operation not permitted".
# Use COPY --chmod to set the executable bit at copy time instead.
COPY --chown=vespa:vespa --chmod=755 entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]


