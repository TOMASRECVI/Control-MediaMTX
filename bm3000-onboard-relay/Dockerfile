# Compila un ffmpeg ESTATICO para ARMv5 (CPU real: Cortex-A9 sin FPU,
# Hi3520D) con soporte SRT, usando un toolchain MUSL (no glibc).
#
# Historial de por que se llego a esta configuracion exacta (cada paso
# se confirmo probando el binario en el equipo real por telnet):
#
#   1. dockcross/linux-armv7 con NEON activado -> "Illegal instruction"
#      al ejecutar. El Cortex-A9 de este SoC no tiene NEON.
#   2. Forzando -mfpu=vfpv3-d16 (VFP basico, sin NEON) -> SIGUE dando
#      "Illegal instruction". El chip no tiene NINGUNA FPU, ni siquiera
#      VFP basico -- coincide con que "box" declara ABI "soft" (no
#      "softfp") en sus atributos ELF.
#   3. Cambiando a dockcross/linux-armv5 (soft-float sin FPU de fabrica)
#      -> compila y arranca sin error de instruccion ilegal, pero ahora
#      falla con "FATAL: kernel too old" -- la GLIBC de ese toolchain
#      exige un kernel >= 4.10, y el equipo corre Linux 3.0.8 (via
#      telnet: uname -r).
#   4. Por eso este Dockerfile usa MUSL en vez de glibc: musl no hace
#      esa comprobacion de version de kernel, esta pensada precisamente
#      para producir binarios estaticos portables entre kernels viejos.
#      El toolchain sale de la imagen messense/rust-musl-cross (Docker
#      Hub) -- musl.cc (la fuente "oficial" de estos toolchains) esta
#      caida/inalcanzable desde los runners de GitHub Actions, así que
#      se usa esta imagen ya publicada con el mismo toolchain dentro.
#
# Uso (en un servidor con Docker, p.ej. 192.168.1.147):
#   docker build -t bm3000-ffmpeg-builder .
#   docker create --name extract bm3000-ffmpeg-builder
#   docker cp extract:/out/ffmpeg_armv7 .
#   docker rm extract
#
# El resultado es un unico fichero "ffmpeg_armv7" que se copia al
# encoder por telnet/ftp (ver README.md).

FROM messense/rust-musl-cross:armv5te-musleabi AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        cmake pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Diagnostico: no tengo memorizado el nombre exacto del binario gcc
# dentro de esta imagen -- lo buscamos en vez de adivinar a ciegas.
RUN echo "--- buscando compiladores cruzados ---"; \
    find / -xdev -iname "*-gcc" -o -iname "*-g++" 2>/dev/null | grep -v "/proc" ; \
    echo "--- variables de entorno relevantes ---"; \
    env | grep -iE "^CC|^CXX|^AR|^TARGET|^CROSS" || true

ENV CROSS_TRIPLE=armv5te-unknown-linux-musleabi
ENV CC=${CROSS_TRIPLE}-gcc
ENV CXX=${CROSS_TRIPLE}-g++
ENV AR=${CROSS_TRIPLE}-ar
ENV RANLIB=${CROSS_TRIPLE}-ranlib

WORKDIR /src

# --- libsrt (Haivision) ---
RUN git clone --depth 1 --branch v1.5.3 https://github.com/Haivision/srt.git srt && \
    cd srt && \
    mkdir build && cd build && \
    cmake .. \
        -DCMAKE_SYSTEM_NAME=Linux \
        -DCMAKE_SYSTEM_PROCESSOR=arm \
        -DCMAKE_C_COMPILER=$CC \
        -DCMAKE_CXX_COMPILER=$CXX \
        -DCMAKE_AR=$(command -v ${AR}) \
        -DCMAKE_RANLIB=$(command -v ${RANLIB}) \
        -DCMAKE_INSTALL_PREFIX=/opt/armv7 \
        -DENABLE_SHARED=OFF \
        -DENABLE_STATIC=ON \
        -DENABLE_APPS=OFF \
        -DENABLE_ENCRYPTION=OFF \
        -DCMAKE_C_FLAGS="-static-libgcc" \
        -DCMAKE_CXX_FLAGS="-static-libgcc -static-libstdc++" \
    && make -j"$(nproc)" && make install

# Sin -DUSE_ENCLIB, con ENABLE_ENCRYPTION=OFF, srt.pc no declara ninguna
# dependencia de OpenSSL -- si se pusieran ambas a la vez, srt.pc queda con
# "Requires.private: openssl" y pkg-config falla al resolverla (no hay
# openssl cross-compilado aqui), y ffmpeg lo reporta como "srt not found"
# sin mas detalle. Verificamos aqui para no repetir ese diagnostico a ciegas.
ENV PKG_CONFIG_PATH=/opt/armv7/lib/pkgconfig
RUN echo "--- pkg-config --exists (sin --static) ---"; \
    pkg-config --exists --print-errors "srt >= 1.3.0" && echo OK || echo FALLO; \
    echo "--- pkg-config --exists --static (esto es lo que usa ffmpeg configure) ---"; \
    pkg-config --exists --print-errors --static "srt >= 1.3.0" && echo OK || echo FALLO; \
    echo "--- srt.pc ---"; cat /opt/armv7/lib/pkgconfig/srt.pc; \
    echo "--- haisrt.pc ---"; cat /opt/armv7/lib/pkgconfig/haisrt.pc || true

# --- ffmpeg (solo lo imprescindible: demux RTSP, mux MPEG-TS, remux, protocolo SRT) ---
RUN git clone --depth 1 --branch n6.1 https://github.com/FFmpeg/FFmpeg.git ffmpeg && \
    cd ffmpeg && \
    (./configure \
        --arch=arm --target-os=linux --cross-prefix=${CROSS_TRIPLE}- \
        --enable-cross-compile \
        --pkg-config=pkg-config \
        --extra-cflags="-I/opt/armv7/include" \
        --extra-ldflags="-L/opt/armv7/lib -static" \
        --disable-neon \
        --extra-libs="-Wl,--start-group -lstdc++ -lgcc -lc -latomic -Wl,--end-group" \
        --pkg-config-flags="--static" \
        --enable-static --disable-shared \
        --enable-gpl --enable-version3 \
        --enable-libsrt \
        --disable-doc --disable-debug --disable-ffplay --disable-ffprobe \
        --disable-avdevice --disable-postproc \
        --disable-everything \
        --enable-ffmpeg \
        --enable-protocol=rtsp,tcp,udp,srt,file \
        --enable-demuxer=rtsp,rtp \
        --enable-muxer=mpegts,rtsp \
        --enable-parser=h264,hevc,aac \
        --enable-decoder=aac \
        --enable-bsf=h264_mp4toannexb \
        --enable-runtime-cpudetect \
     || (echo "--- ffbuild/config.log (tail -n 200) ---"; tail -n 200 ffbuild/config.log; false)) \
    && make -j"$(nproc)"

RUN mkdir -p /out && cp /src/ffmpeg/ffmpeg /out/ffmpeg_armv7 && \
    ${CROSS_TRIPLE}-strip /out/ffmpeg_armv7

FROM scratch AS export
COPY --from=build /out/ffmpeg_armv7 /ffmpeg_armv7
CMD ["/ffmpeg_armv7"]
