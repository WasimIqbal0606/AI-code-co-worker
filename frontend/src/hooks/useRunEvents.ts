/**
 * SSE hook — subscribes to run events in real-time.
 * Includes smart preflight check and immediate 404 handling.
 */

"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { AgentEvent } from "@/types/schemas";
import { getEventsUrl } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useRunEvents(runId: string | null) {
    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [isDone, setIsDone] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const sourceRef = useRef<EventSource | null>(null);
    const retriesRef = useRef(0);
    const stoppedRef = useRef(false);
    const MAX_RETRIES = 3;

    const connect = useCallback(() => {
        if (!runId || stoppedRef.current) return;

        // Close existing connection
        if (sourceRef.current) {
            sourceRef.current.close();
        }

        const url = getEventsUrl(runId);
        const source = new EventSource(url);
        sourceRef.current = source;

        source.onopen = () => {
            setIsConnected(true);
            retriesRef.current = 0; // reset retries on successful connection
        };

        const handleEvent = (e: MessageEvent) => {
            try {
                const event: AgentEvent = JSON.parse(e.data);
                setEvents((prev) => [...prev, event]);

                if (
                    event.event_type === "supervisor_done" ||
                    event.event_type === "error"
                ) {
                    setIsDone(true);
                    source.close();
                    setIsConnected(false);
                    stoppedRef.current = true;
                }
            } catch {
                // Ignore parse errors
            }
        };

        // Listen to all event types
        const eventTypes = [
            "supervisor_started",
            "agent_started",
            "agent_progress",
            "agent_done",
            "supervisor_done",
            "error",
        ];

        eventTypes.forEach((type) => {
            source.addEventListener(type, handleEvent);
        });

        // Also listen to generic message events
        source.onmessage = handleEvent;

        source.onerror = () => {
            source.close();
            setIsConnected(false);

            // Don't reconnect if already done or stopped
            if (isDone || stoppedRef.current) return;

            retriesRef.current += 1;

            if (retriesRef.current >= MAX_RETRIES) {
                // After MAX_RETRIES, check if the run actually exists
                // before showing error. This prevents false alarms
                // during brief network hiccups.
                fetch(`${API_BASE}/run/${runId}/result`)
                    .then((res) => {
                        if (res.status === 404) {
                            stoppedRef.current = true;
                            setError("This run no longer exists. The server was restarted.");
                            setIsDone(true);
                        } else if (res.ok) {
                            // Run exists but SSE failed — try to load result directly
                            res.json().then((data) => {
                                if (data.status === "completed" || data.status === "failed") {
                                    stoppedRef.current = true;
                                    setIsDone(true);
                                } else {
                                    // Still running — one more retry
                                    setTimeout(() => connect(), 3000);
                                }
                            });
                        } else {
                            stoppedRef.current = true;
                            setError("Server error. Please try again.");
                            setIsDone(true);
                        }
                    })
                    .catch(() => {
                        stoppedRef.current = true;
                        setError("Cannot reach the backend server. Is it running?");
                        setIsDone(true);
                    });
            } else {
                // Quick retry with backoff
                setTimeout(() => connect(), 1000 * retriesRef.current);
            }
        };
    }, [runId, isDone]);

    useEffect(() => {
        if (!runId) return;

        stoppedRef.current = false;

        // Preflight check: verify the run exists before opening SSE.
        // This gives us an immediate, clean error on 404 instead of
        // burning through retries with the EventSource retry loop.
        fetch(`${API_BASE}/run/${runId}/result`)
            .then((res) => {
                if (res.status === 404) {
                    stoppedRef.current = true;
                    setError("This run no longer exists. The server was restarted.");
                    setIsDone(true);
                } else {
                    // Run exists — check if already completed
                    res.json().then((data) => {
                        if (data.status === "completed" || data.status === "failed") {
                            // Run already finished — just mark done, result will load via page effect
                            setIsDone(true);
                        } else {
                            // Run is still active — connect to SSE stream
                            connect();
                        }
                    }).catch(() => {
                        // JSON parse failed but run exists — connect SSE
                        connect();
                    });
                }
            })
            .catch(() => {
                // Backend unreachable entirely
                stoppedRef.current = true;
                setError("Cannot reach the backend server. Is it running?");
                setIsDone(true);
            });

        return () => {
            sourceRef.current?.close();
            stoppedRef.current = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [runId]);

    const reset = useCallback(() => {
        setEvents([]);
        setIsDone(false);
        setIsConnected(false);
        setError(null);
        retriesRef.current = 0;
        stoppedRef.current = false;
    }, []);

    return { events, isConnected, isDone, error, reset };
}
