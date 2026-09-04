FROM postgres:16-alpine
RUN apk add --no-cache gnupg curl bash
COPY backup.sh /backup.sh
COPY restore.sh /restore.sh
RUN chmod +x /backup.sh /restore.sh
ENTRYPOINT ["/backup.sh"]
