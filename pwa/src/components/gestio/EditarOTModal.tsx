"use client";

import React from "react";
import { Fulla360OTModal } from "@/components/gestio/Fulla360OTModal";

interface EditarOTModalProps {
  feinaId: string;
  onClose: () => void;
  onSuccess?: () => void;
}

/**
 * Wrapper unificat sobre l'únic model de Fulla 360° d'OT (mode="EDIT").
 */
export function EditarOTModal({ feinaId, onClose, onSuccess }: EditarOTModalProps) {
  return (
    <Fulla360OTModal
      mode="EDIT"
      isOpen={true}
      feinaId={feinaId}
      onClose={onClose}
      onSuccess={() => onSuccess?.()}
    />
  );
}
