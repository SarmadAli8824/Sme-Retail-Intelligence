FROM postgres:16-alpine
RUN apk add --no-cache gnupg curl bash
COPY backup.sh /backup.sh
RUN chmod +x /backup.sh
ENTRYPOINT ["/backup.sh"]

