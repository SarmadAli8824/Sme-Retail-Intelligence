FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY . .
RUN go mod tidy && CGO_ENABLED=0 go build -o /worker ./cmd/worker
FROM alpine:3.21
RUN adduser -D app
USER app
COPY --from=build /worker /worker
CMD ["/worker"]
