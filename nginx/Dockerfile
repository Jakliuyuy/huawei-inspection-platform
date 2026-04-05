FROM node:22-alpine AS web-build

WORKDIR /web

COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

FROM nginx:1.27-alpine

# 清除默认配置并拷贝我们的模块化配置
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/conf.d/*.conf /etc/nginx/conf.d/
COPY --from=web-build /web/dist /usr/share/nginx/html/app
