# 🚀 Instalación de MediaMTX Recording Manager

Guía para desplegar este panel junto a **cualquier** servidor MediaMTX que ya
tengas corriendo en Docker. No necesitas tocar nada de tu configuración
existente de MediaMTX.

## Requisitos previos

- Docker y Docker Compose instalados en el servidor.
- Un contenedor de MediaMTX ya en ejecución (`docker ps` debe mostrarlo).

## Pasos

### 1. Clona el repositorio en el servidor

```bash
git clone https://github.com/TOMASRECVI/Control-MediaMTX.git
cd Control-MediaMTX/install
```

### 2. Averigua los datos de tu contenedor MediaMTX

```bash
# Nombre del contenedor
docker ps | grep mediamtx

# Red que usa
docker inspect <nombre-contenedor-mediamtx> \
  --format '{{range $net,$conf := .NetworkSettings.Networks}}{{$net}}{{end}}'

# Volumen de datos/grabaciones
docker inspect <nombre-contenedor-mediamtx> \
  --format '{{range .Mounts}}{{.Name}}{{"\n"}}{{end}}'
```

### 3. Configura tu instalación

```bash
cp .env.example .env
nano .env   # o el editor que prefieras
```

Rellena en `.env`:
- `MEDIAMTX_API` — con el nombre real de tu contenedor MediaMTX (puerto API, normalmente 9997).
- `MEDIAMTX_NETWORK` — la red obtenida en el paso 2.
- `MEDIAMTX_DATA_VOLUME` — el volumen obtenido en el paso 2.
- `AUTH_USERNAME` / `AUTH_PASSWORD` — las credenciales de acceso al panel. **Cambia la contraseña de ejemplo.**
- `MANAGER_PORT` — puerto donde quieres exponer el panel (por defecto 8080).

### 4. Despliega

```bash
docker compose up -d --build
```

### 5. Accede al panel

```
http://<ip-de-tu-servidor>:<MANAGER_PORT>
```

Inicia sesión con el usuario y contraseña que configuraste en `.env`.

## Actualizar a una versión nueva

```bash
git pull
docker compose up -d --build
```

## Solución de problemas

| Problema | Causa probable |
|---|---|
| El panel no conecta con MediaMTX | `MEDIAMTX_API` apunta a un contenedor/puerto incorrecto. Revisa el nombre con `docker ps`. |
| Error al arrancar por red/volumen inexistente | `MEDIAMTX_NETWORK` o `MEDIAMTX_DATA_VOLUME` no coinciden con los reales. Repite el paso 2. |
| No recuerdas la contraseña generada automáticamente | Si dejaste `AUTH_PASSWORD` vacío, revisa `docker logs mediamtx-manager` justo después de arrancar — se imprime una sola vez. |

Para más detalles sobre las funciones del panel, consulta el [README principal](../README.md).
