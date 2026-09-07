# Rediseño integral de la mascota

## Diagnóstico

El adelgazado anterior hizo más evidente la cabeza desproporcionada, el torso con forma de recipiente y los accesorios separados del cuerpo. Había materiales incompatibles entre pelo plano, piel sombreada y tuberías. La marca competía con ojos, manómetro, boquilla, aros y botas. Los controles tenían dos acciones principales contradictorias (Iniciar y Pausar visibles a la vez), subpáginas sin regreso y altura fija.

## Nueva dirección

Técnico de riego anime con uniforme continuo verde, guantes marfil, una herramienta de medición y postura relajada. El logo original de Camposol se compone sobre la insignia del uniforme y permanece visible en los controles. La imagen base conserva sus píxeles originales en `assets/mascot/technician-sheet.png`.

El personaje es una ilustración con acabado 3D animada con dos sprites (ojos abiertos/cerrados), inclinación limitada y respiración suave. No es un modelo 3D que se pueda orbitar. Esta presentación sustituye el antiguo ensamblaje de polígonos; el recolector y sus APIs no cambian.

El generador entregó un fondo cuadriculado opaco incluso tras pedir transparencia. `companion_art.py` aplica una máscara únicamente para su presentación en el escritorio: elimina el exterior claro neutro conectado al borde y conserva los detalles claros encerrados. El recurso original permanece intacto. No se interpreta ningún instrumento ilustrado como lectura real.

## Interfaz

- Una sola ventana con controles desplegables bajo el personaje.
- Botón único Iniciar/Pausar automático; Sincronizar ahora secundario.
- Sincronizar desactivado mientras hay un ciclo en curso.
- Cabecera con marca original y estado del recolector.
- Ajustes y Actividad con regreso al estado.
- Altura adaptada a pantalla y contenido desplazable.
- Se conserva la protección de no enviar datos al abrir y el cierre después del ciclo activo.

## Verificación

Se revisaron visualmente la ilustración y ambas poses sobre un fondo de escritorio. Se verificaron apertura, configuración, barra de desplazamiento, regreso, actividad, repliegue, etiquetas de inicio/pausa, desactivación durante envío y ausencia de ventanas secundarias. Las consultas reales y WhatsApp no se activaron durante estas pruebas.

## Generación del arte

Se usó la herramienta integrada `image_gen`, sin API de pago configurada ni CLI. El primer prompt solicitó un técnico anime de riego con uniforme verde, guantes marfil, botas burdeos, cabello negro, una herramienta, distintivo circular vacío y acabado 3D suave, aislado sobre transparencia. Se descartó el ensamblaje de piezas y se pidió una silueta coherente legible a 240 píxeles.

Prompt final aplicado al recurso de animación:

> Precise production sprite edit of the supplied image. KEEP the same technician character, proportions, clothing, tool, face, hair, pose and lighting. Make a two-frame animation sheet: exactly two identical full-body copies of this character side by side, same scale, baseline and placement within each half. Left character eyes open exactly like source. Right character same exact pose with both eyelids gently CLOSED for a natural blink; absolutely no other changes. CRITICAL: REMOVE the checkerboard pattern completely. Output real PNG transparency using an alpha channel, with empty pixels around the figures. The input checkerboard is a baked background that must be removed; do NOT paint any checkerboard, gray squares, white backdrop, floor, labels, borders, or shadows. Both figures fully visible, with equal generous transparent margins; each centered in its own half. Preserve the empty circular badge for logo compositing. True RGBA background, not a visual simulation of transparency.
