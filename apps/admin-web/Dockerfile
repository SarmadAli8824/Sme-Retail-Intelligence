FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npx ng build
FROM nginx:1.27-alpine
COPY --from=build /app/dist/admin-web/browser /usr/share/nginx/html
EXPOSE 80

