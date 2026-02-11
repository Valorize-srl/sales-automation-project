FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

RUN npm run build

# Copy standalone output and static files
RUN cp -r .next/standalone/* . && cp -r .next/static .next/static

EXPOSE ${PORT:-3000}

CMD sh -c "PORT=${PORT:-3000} node server.js"
