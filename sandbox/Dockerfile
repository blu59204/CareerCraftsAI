FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-sandbox socat ca-certificates fonts-liberation tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 browser
COPY start.sh /opt/browser/start.sh
RUN chmod 755 /opt/browser/start.sh
USER browser
EXPOSE 9222
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/browser/start.sh"]
