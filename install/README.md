# 🚀 Instalación de MediaMTX Recording Manager

Guía para desplegar este panel junto a **cualquier** servidor MediaMTX que ya
tengas corriendo en Docker. No necesitas tocar nada de tu configuración
existente de MediaMTX.

La imagen ya construida está publicada en GitHub Container Registry:

```bash
docker pull ghcr.io/tomasrecvi/control-mediamtx:latest
```

(Se reconstruye automáticamente en cada actualización del proyecto — no
hace falta compilar nada tú mismo, aunque también puedes hacerlo si
prefieres partir del código fuente.)

## Requisitos previos

- Docker y Docker Compose instalados en el servidor.
- Un contenedor de MediaMTX ya en ejecución (`docker ps` debe mostrarlo).

## Pasos

### 1. Descarga el archivo de despliegue

Solo necesitas dos archivos de este repositorio, no hace falta clonarlo
entero:

```bash
mkdir control-mediamtx && cd control-mediamtx
curl -O https://raw.githubusercontent.com/TOMASRECVI/Control-MediaMTX/main/install/docker-compose.yml
curl -O https://raw.githubusercontent.com/TOMASRECVI/Control-MediaMTX/main/install/.env.example
```

(Si prefieres partir del código para poder modificarlo, clona el repo
entero en su lugar: `git clone https://github.com/TOMASRECVI/Control-MediaMTX.git && cd Control-MediaMTX/install`)

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
- `AUTH_USERNAME` / `AUTH_PASSWORD` — credenciales **iniciales** de acceso al panel (por defecto `admin` / `admin`). Solo se usan la primera vez que arranca; después se guardan aparte y se pueden cambiar desde el propio panel sin volver a tocar este archivo (ver paso 5).
- `MANAGER_PORT` — puerto donde quieres exponer el panel (por defecto 8080).

### 4. Despliega

```bash
docker compose pull   # baja la imagen ya construida
docker compose up -d
```

Si en su lugar clonaste el repo y prefieres compilar tú mismo desde el
código: `docker compose up -d --build`.

### 5. Accede al panel

```
http://<ip-de-tu-servidor>:<MANAGER_PORT>
```

Inicia sesión con `admin` / `admin` (o los valores que hayas puesto en
`.env`). **Cámbialos cuanto antes** desde el botón **⚙ Configuración** del
propio panel — no hace falta editar ningún archivo ni reiniciar el
contenedor, el cambio queda guardado.

## Actualizar a una versión nueva

```bash
docker compose pull
docker compose up -d
```

## Solución de problemas

| Problema | Causa probable |
|---|---|
| El panel no conecta con MediaMTX | `MEDIAMTX_API` apunta a un contenedor/puerto incorrecto. Revisa el nombre con `docker ps`. |
| Error al arrancar por red/volumen inexistente | `MEDIAMTX_NETWORK` o `MEDIAMTX_DATA_VOLUME` no coinciden con los reales. Repite el paso 2. |
| No recuerdas la contraseña que pusiste desde el panel | No hay forma de recuperarla desde la interfaz. Bórrala del volumen de datos y reinicia para volver a `admin`/`admin` (o lo que pongas en `.env`): `docker exec mediamtx-manager rm /data/.manager_credentials.json && docker restart mediamtx-manager` |

Para más detalles sobre las funciones del panel, consulta el [README principal](../README.md).
