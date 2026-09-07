# Mascota compacta trabajando en PC

La escena ocupa 230 × 210 píxeles en reposo, frente a los 420 × 340 anteriores. El mismo personaje está sentado frente a computadora, teclado y escritorio. El recurso original se conserva en `assets/mascot/desk-sheet.png`, generado con la herramienta integrada `image_gen` a partir del técnico existente.

El personaje respira, mueve ligeramente la cabeza y parpadea mediante transiciones continuas, a unos 30 fotogramas por segundo. Durante un ciclo aparecen pequeños gestos de tecleo, con pausas de lectura y aceleración progresiva. Se utiliza una pose estable y solo los párpados de otra; la mesa, la computadora y las patas no alternan entre ilustraciones completas. Los gestos son decorativos, no mediciones de riego.

El estado está en una burbuja de pensamiento sobre la cabeza. Ámbar significa espera o primera lectura; verde, contacto reciente confirmado con Supabase; rojo, un ciclo fallido o un intento que no pudo iniciarse. El verde caduca entre 90 y 300 segundos según el intervalo configurado, y se invalida al guardar ajustes de conexión. Una pausa voluntaria sin fallo queda ámbar. El rojo persiste hasta un éxito o una nueva configuración. No indica la salud física de válvulas ni que toda la cola haya sido enviada.

La burbuja contiene un botón nativo: al pulsarlo o presionar Enter/Espacio se abren los mismos controles. Se retiró la barra inferior de estado y se mantuvo la ventana compacta de 230 × 210 píxeles. La opción Reducir movimiento congela los gestos, pero continúa actualizando texto y color. Las imágenes Tk se reutilizan; no se almacena una imagen por cada instante de animación.

Los controles continúan en una sola ventana. Se despliegan arriba si abajo no hay espacio, con alineación que mantiene la posición global de la escena. El ancho crece a 420 píxeles para conservar la legibilidad de los formularios. Se verificaron expansión/repliegue junto a ambos bordes, tamaño compacto, navegación, desplazamiento y desactivación de Sincronizar durante el trabajo.

El logotipo del escritorio se compone con el archivo original de Camposol, sin regenerar el texto. El arte generado se preserva intacto y se aplica transparencia únicamente para mostrarlo en la aplicación.

## Prompt del arte

Se solicitó a la herramienta integrada mantener exactamente el técnico anime existente (cabello negro, ojos verdes, uniforme verde, protecciones marfil y botas burdeos), sentado a una mesa con computadora y teclado. Cuatro celdas iguales en una cuadrícula 2×2, con cámara, luz, escala y mobiliario idénticos: manos en teclado leyendo; dedos derechos ligeramente elevados; dedos izquierdos elevados; pose inicial con ojos cerrados. Se pidió retirar la herramienta de campo, dejar la pantalla sin datos ni palabras, conservar una insignia circular vacía para colocar el logo original, fondo blanco liso para la presentación en escritorio y márgenes iguales. No se utilizó CLI de imágenes ni se activaron conexiones de Dream durante las pruebas.

## Auditoría de rendimiento y accesibilidad

La revisión del 6/09/2026 conserva la escena pequeña y añade controles nativos con teclado, estado de error visible al minimizar, panel desplazable completo y preferencias de movimiento reducido, texto grande, barra de título y siempre visible. Enter abre controles; Escape minimiza; Tab recorre acciones. Ejecutar otra vez el lanzador recupera la ventana existente; `-Controls` la abre directamente con controles.

El atlas `assets/mascot/desk-sprites.png` ya contiene el recorte y el logo proporcional. Se regenera con `python scripts/prepare_companion.py`. La carga no ejecuta floodfill: primera carga medida 12,1 ms frente a 1.725 ms de preparación anterior. La animación continua posterior tarda aproximadamente 2,7–3,4 ms por fotograma en la medición local; el microbenchmark de dibujos estáticos de la auditoría anterior no describe este nuevo movimiento. El informe completo y los límites de producción están en [Auditoría integral](AUDITORIA_INTEGRAL_2026-09-06.md).
