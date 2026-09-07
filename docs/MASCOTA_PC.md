# Mascota compacta trabajando en PC

La escena ocupa 230 × 210 píxeles en reposo, frente a los 420 × 340 anteriores. El mismo personaje está sentado frente a computadora, teclado y escritorio. El recurso original se conserva en `assets/mascot/desk-sheet.png`, generado con la herramienta integrada `image_gen` a partir del técnico existente.

Cuatro poses registradas representan lectura, dos posiciones de tecleo y parpadeo. Se usa una caja común de recorte y un anclaje a la base para estabilizar la mesa. Los gestos son decorativos: en espera son lentos; durante un ciclo real son más rápidos y aparece el indicador DREAM. Ninguna animación se presenta como medición real de riego.

Los controles continúan en una sola ventana. Se despliegan arriba si abajo no hay espacio, con alineación que mantiene la posición global de la escena. El ancho crece a 420 píxeles para conservar la legibilidad de los formularios. Se verificaron expansión/repliegue junto a ambos bordes, tamaño compacto, navegación, desplazamiento y desactivación de Sincronizar durante el trabajo.

El logotipo del escritorio se compone con el archivo original de Camposol, sin regenerar el texto. El arte generado se preserva intacto y se aplica transparencia únicamente para mostrarlo en la aplicación.

## Prompt del arte

Se solicitó a la herramienta integrada mantener exactamente el técnico anime existente (cabello negro, ojos verdes, uniforme verde, protecciones marfil y botas burdeos), sentado a una mesa con computadora y teclado. Cuatro celdas iguales en una cuadrícula 2×2, con cámara, luz, escala y mobiliario idénticos: manos en teclado leyendo; dedos derechos ligeramente elevados; dedos izquierdos elevados; pose inicial con ojos cerrados. Se pidió retirar la herramienta de campo, dejar la pantalla sin datos ni palabras, conservar una insignia circular vacía para colocar el logo original, fondo blanco liso para la presentación en escritorio y márgenes iguales. No se utilizó CLI de imágenes ni se activaron conexiones de Dream durante las pruebas.

## Auditoría de rendimiento y accesibilidad

La revisión del 6/09/2026 conserva la escena pequeña y añade controles nativos con teclado, estado de error visible al minimizar, panel desplazable completo y preferencias de movimiento reducido, texto grande, barra de título y siempre visible. Enter abre controles; Escape minimiza; Tab recorre acciones. Ejecutar otra vez el lanzador recupera la ventana existente; `-Controls` la abre directamente con controles.

El atlas `assets/mascot/desk-sprites.png` ya contiene el recorte y el logo proporcional. Se regenera con `python scripts/prepare_companion.py`. La carga no ejecuta floodfill: primera carga medida12,1ms frente1.725ms de preparación anterior. El informe completo, regresiones y límites de producción están en [Auditoría integral](AUDITORIA_INTEGRAL_2026-09-06.md).
