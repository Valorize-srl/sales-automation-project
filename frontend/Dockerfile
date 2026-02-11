FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

RUN npm run build

RUN cp -r .next/standalone/* . && cp -r .next/static .next/static

CMD sh -c "echo 'PORT is:' $PORT && node server.js"
