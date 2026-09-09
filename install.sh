#!/bin/bash

# MediaMTX Recording Manager - Quick Install Script
# Este script facilita la instalación y configuración

set -e  # Exit on any error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   MediaMTX Recording Manager - Script de Instalación          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
echo -e "${BLUE}1. Verificando Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker no está instalado${NC}"
    echo "Por favor instala Docker desde: https://docs.docker.com/engine/install/"
    exit 1
fi
echo -e "${GREEN}✓ Docker está instalado${NC}"
echo

# Check if Docker Compose is installed
echo -e "${BLUE}2. Verificando Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose no está instalado${NC}"
    echo "Por favor instala Docker Compose"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose está instalado${NC}"
echo

# List MediaMTX containers
echo -e "${BLUE}3. Buscando contenedor MediaMTX...${NC}"
MEDIAMTX_CONTAINER=$(docker ps --format "table {{.Names}}" | grep mediamtx | head -1)

if [ -z "$MEDIAMTX_CONTAINER" ]; then
    echo -e "${YELLOW}⚠ No se encontró contenedor MediaMTX en ejecución${NC}"
    echo "Contenedores disponibles:"
    docker ps --format "table {{.Names}}\t{{.Image}}"
    echo
    read -p "Ingresa el nombre del contenedor MediaMTX: " MEDIAMTX_CONTAINER
fi

if [ -z "$MEDIAMTX_CONTAINER" ]; then
    echo -e "${RED}✗ Se requiere un contenedor MediaMTX${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Contenedor encontrado: $MEDIAMTX_CONTAINER${NC}"
echo

# Get MediaMTX network
echo -e "${BLUE}4. Buscando red de MediaMTX...${NC}"
MEDIAMTX_NETWORK=$(docker inspect "$MEDIAMTX_CONTAINER" --format='{{range $net, $conf := .NetworkSettings.Networks}}{{$net}} {{end}}' | awk '{print $1}')

if [ -z "$MEDIAMTX_NETWORK" ]; then
    echo -e "${RED}✗ No se pudo determinar la red${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Red encontrada: $MEDIAMTX_NETWORK${NC}"
echo

# Get MediaMTX volume
echo -e "${BLUE}5. Buscando volumen de datos...${NC}"
MEDIAMTX_VOLUME=$(docker inspect "$MEDIAMTX_CONTAINER" --format='{{range .Mounts}}{{if eq .Destination "/recordings"}}{{.Name}}{{end}}{{end}}')

if [ -z "$MEDIAMTX_VOLUME" ]; then
    MEDIAMTX_VOLUME=$(docker inspect "$MEDIAMTX_CONTAINER" --format='{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')
fi

if [ -z "$MEDIAMTX_VOLUME" ]; then
    echo -e "${YELLOW}⚠ No se encontró volumen estándar${NC}"
    echo "Volúmenes disponibles:"
    docker inspect "$MEDIAMTX_CONTAINER" --format='{{range .Mounts}}{{.Name}}{{"\n"}}{{end}}'
    echo
    read -p "Ingresa el nombre del volumen de datos: " MEDIAMTX_VOLUME
fi

if [ -z "$MEDIAMTX_VOLUME" ]; then
    echo -e "${YELLOW}⚠ Advertencia: No se especificó volumen${NC}"
    MEDIAMTX_VOLUME="mediamtx_data"
fi

echo -e "${GREEN}✓ Volumen: $MEDIAMTX_VOLUME${NC}"
echo

# Port selection
echo -e "${BLUE}6. Seleccionando puerto...${NC}"
DEFAULT_PORT=8080
read -p "Puerto para acceder a la interfaz (por defecto $DEFAULT_PORT): " SELECTED_PORT
SELECTED_PORT=${SELECTED_PORT:-$DEFAULT_PORT}

echo -e "${GREEN}✓ Puerto seleccionado: $SELECTED_PORT${NC}"
echo

# Backup existing docker-compose.yml
if [ -f docker-compose.yml ]; then
    echo -e "${BLUE}7. Haciendo backup de docker-compose.yml...${NC}"
    cp docker-compose.yml docker-compose.yml.backup
    echo -e "${GREEN}✓ Backup guardado como docker-compose.yml.backup${NC}"
    echo
fi

# Generate docker-compose.yml
echo -e "${BLUE}8. Actualizando docker-compose.yml...${NC}"

cat > docker-compose.yml << EOF
# ------------------------------------------------------------------
#  MediaMTX Recording Manager
#  Despliega junto al contenedor mediamtx existente.
#
#  NOTA: Tu contenedor MediaMTX se llama "$MEDIAMTX_CONTAINER"
#        y usa la red "$MEDIAMTX_NETWORK"
#        con el volumen "$MEDIAMTX_VOLUME"
# ------------------------------------------------------------------

services:
  mediamtx-manager:
    build: .
    container_name: mediamtx-manager
    restart: unless-stopped
    ports:
      - "$SELECTED_PORT:8080"
    environment:
      MEDIAMTX_API: "http://$MEDIAMTX_CONTAINER:9997"
    volumes:
      - $MEDIAMTX_VOLUME:/data
    networks:
      - $MEDIAMTX_NETWORK

networks:
  $MEDIAMTX_NETWORK:
    external: true

volumes:
  $MEDIAMTX_VOLUME:
    external: true
EOF

echo -e "${GREEN}✓ docker-compose.yml actualizado${NC}"
echo

# Build and start
echo -e "${BLUE}9. Construyendo e iniciando contenedor...${NC}"
docker compose up -d --build

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Contenedor iniciado correctamente${NC}"
else
    echo -e "${RED}✗ Error al iniciar el contenedor${NC}"
    echo "Consulta los logs con: docker logs mediamtx-manager"
    exit 1
fi
echo

# Wait for service to be ready
echo -e "${BLUE}10. Esperando a que el servicio esté listo...${NC}"
sleep 3

# Test connectivity
echo -e "${BLUE}11. Probando conectividad...${NC}"
if curl -s http://127.0.0.1:$SELECTED_PORT/api/health > /dev/null; then
    echo -e "${GREEN}✓ Servicio está respondiendo${NC}"
else
    echo -e "${YELLOW}⚠ Servicio no responde todavía (puede estar iniciando)${NC}"
    sleep 2
fi
echo

# Final message
echo "╔════════════════════════════════════════════════════════════════╗"
echo -e "║${GREEN}   ✓ Instalación completada${NC}                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo
echo -e "${BLUE}Accede a la interfaz web en:${NC}"
echo -e "  ${GREEN}http://127.0.0.1:$SELECTED_PORT${NC}"
echo
echo -e "${BLUE}O desde otra máquina:${NC}"
echo -e "  ${GREEN}http://$(hostname -I | awk '{print $1}'):$SELECTED_PORT${NC}"
echo
echo -e "${BLUE}Comandos útiles:${NC}"
echo "  Ver logs:         docker logs mediamtx-manager -f"
echo "  Parar:            docker compose down"
echo "  Reiniciar:        docker compose up -d"
echo "  Diagnosticar:     docker exec mediamtx-manager bash /app/debug_api.sh"
echo
echo -e "${YELLOW}Más información en: INSTRUCCIONES.md${NC}"
