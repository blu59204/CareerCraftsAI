FROM alpine:3.23
RUN apk add --no-cache openssh-client
COPY tunnel.sh /tunnel.sh
CMD ["sh", "/tunnel.sh"]
