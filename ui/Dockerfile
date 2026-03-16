FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .

# Vite env vars are baked at build time — pass via Docker build arg
ARG VITE_ENGINE_URL=http://localhost:8000
ENV VITE_ENGINE_URL=$VITE_ENGINE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
