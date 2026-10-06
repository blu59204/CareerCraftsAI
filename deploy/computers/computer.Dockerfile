FROM careercraft-computer:b6932d3
COPY harden-computer.mjs /tmp/harden-computer.mjs
RUN bun /tmp/harden-computer.mjs /app/src/index.ts && rm /tmp/harden-computer.mjs
