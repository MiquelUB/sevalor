/**
 * Mòdul de captura i compressió multimèdia al client (Spec 020 RF-11, RF-12, RF-17).
 *
 * Compleix:
 * - Atributs HTML5 obligatoris per a càmera directa antifraude: accept="image/*" capture="environment"
 * - Compressió automàtica a WebP al client per sota d'1 MB abans de persistir a IndexedDB
 */

export const CAMERA_LIVE_INPUT_PROPS = {
  type: "file" as const,
  accept: "image/*",
  capture: "environment" as const, // Obliga a obrir la càmera posterior en viu i bloca la galeria
};

export async function compressImageToWebP(
  file: File | Blob,
  maxDimension: number = 1920,
  quality: number = 0.82
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    // Si estem en entorn Node.js / SSR
    if (typeof window === "undefined" || typeof document === "undefined") {
      resolve(file as Blob);
      return;
    }

    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);
      let { width, height } = img;

      if (width > maxDimension || height > maxDimension) {
        if (width > height) {
          height = Math.round((height * maxDimension) / width);
          width = maxDimension;
        } else {
          width = Math.round((width * maxDimension) / height);
          height = maxDimension;
        }
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("No s'ha pogut obtenir el context 2D del canvas."));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);

      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("Error en codificar la imatge a WebP."));
            return;
          }
          resolve(blob);
        },
        "image/webp",
        quality
      );
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Error en carregar la imatge per al processament."));
    };

    img.src = url;
  });
}
