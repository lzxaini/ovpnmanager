FROM node:18-alpine

# Install bash and other dependencies
RUN apk add --no-cache bash curl openssl easy-rsa openvpn socat

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --only=production

# Copy application files
COPY . .

# Create directory for client configs
RUN mkdir -p /root/clients

EXPOSE 3000

CMD ["node", "server.js"]
