# Revisión visual del robot

Problemas encontrados: aristas dentadas al dibujar polígonos directamente en Tk; casco, cuerpo y accesorios con materiales demasiado parecidos; visor plano; botones principales y secundarios con el mismo peso; ausencia de respuesta al pasar el cursor y de foco visible.

Cambios: renderizado a triple resolución con reducción antialias, mayor detalle de malla, carcasa marfil con remates verdes, visor oscuro con reflejo, acoples metálicos dorados, manguera de riego, detalles de servicio y ojos luminosos. Paleta inspirada en la referencia Camposol. Se conserva una única ventana con controles desplegables, foco de teclado y estados de hover.

La imagen renderizada se revisó visualmente. Se comprobaron apertura, ajustes, actividad, repliegue y animación. Los fotogramas se almacenan en una caché limitada de 64 entradas para evitar recalcular la geometría en cada actualización; el movimiento vertical se aplica al componer la imagen. El primer fotograma de una pose requiere más tiempo que uno almacenado.

La animación de agua indica trabajo del recolector; no representa una válvula real abierta. No se modificó la lectura de Dream ni el envío a Supabase.
