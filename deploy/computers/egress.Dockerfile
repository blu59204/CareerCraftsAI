FROM alpine:3.23
RUN apk add --no-cache squid
COPY squid.conf /etc/squid/squid.conf
CMD ["squid", "-N", "-f", "/etc/squid/squid.conf"]
