"use client";

import React, { useState, useEffect } from "react";
import { useLiveQuery } from "dexie-react-hooks";
import { db } from "@/lib/offline/db";

export default function NotificationCenter() {
    const failedSyncs = useLiveQuery(
        () => db.sync_queue.where("status").equals("failed").toArray(),
        []
    );

    const pendingSyncs = useLiveQuery(
        () => db.sync_queue.where("status").equals("pending").toArray(),
        []
    );

    const [isOnline, setIsOnline] = useState(true);

    useEffect(() => {
        setIsOnline(navigator.onLine);
        const handleOnline = () => setIsOnline(true);
        const handleOffline = () => setIsOnline(false);

        window.addEventListener("online", handleOnline);
        window.addEventListener("offline", handleOffline);
        return () => {
            window.removeEventListener("online", handleOnline);
            window.removeEventListener("offline", handleOffline);
        };
    }, []);

    if (!failedSyncs && !pendingSyncs && isOnline) return null;

    const hasFailed = failedSyncs && failedSyncs.length > 0;
    const hasPending = pendingSyncs && pendingSyncs.length > 0;

    if (!hasFailed && !hasPending && isOnline) return null;

    return (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
            {!isOnline && (
                <div className="bg-yellow-500/10 border border-yellow-500/50 text-yellow-700 px-4 py-3 rounded-lg shadow-lg flex items-start">
                    <div className="flex-1">
                        <p className="font-semibold text-sm">Mode Offline</p>
                        <p className="text-xs mt-1">
                            Estàs treballant sense connexió. Les dades es sincronitzaran quan tornis a tenir xarxa.
                        </p>
                    </div>
                </div>
            )}
            
            {hasFailed && (
                <div className="bg-red-500/10 border border-red-500/50 text-red-700 px-4 py-3 rounded-lg shadow-lg flex items-start">
                    <div className="flex-1">
                        <p className="font-semibold text-sm">Error de sincronització</p>
                        <p className="text-xs mt-1">
                            {failedSyncs.length} accions no s'han pogut enviar al servidor.
                        </p>
                    </div>
                </div>
            )}

            {hasPending && isOnline && (
                <div className="bg-blue-500/10 border border-blue-500/50 text-blue-700 px-4 py-3 rounded-lg shadow-lg flex items-start">
                    <div className="flex-1">
                        <p className="font-semibold text-sm">Sincronitzant...</p>
                        <p className="text-xs mt-1">
                            {pendingSyncs.length} accions pendents d'enviar.
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
