import { useCallback, useState } from "react";
import type { ConversionJob } from "./conversionApi";

export interface UseConversionJobsState {
  jobs: ConversionJob[];
  addJob: (job: ConversionJob) => void;
  updateJob: (id: string, updates: Partial<ConversionJob>) => void;
  clearCompleted: () => void;
}

/**
 * Manages the state of conversion jobs.
 * Each job tracks: queued → running (with progress) → success or error.
 * Progress events followed by error results are tolerated (see job state machine in brief).
 */
export function useConversionJobs(): UseConversionJobsState {
  const [jobs, setJobs] = useState<ConversionJob[]>([]);

  const addJob = useCallback((job: ConversionJob) => {
    setJobs((prev) => [...prev, job]);
  }, []);

  const updateJob = useCallback(
    (id: string, updates: Partial<ConversionJob>) => {
      setJobs((prev) =>
        prev.map((job) => (job.id === id ? { ...job, ...updates } : job)),
      );
    },
    [],
  );

  const clearCompleted = useCallback(() => {
    setJobs((prev) =>
      prev.filter((job) => job.status === "queued" || job.status === "running"),
    );
  }, []);

  return { jobs, addJob, updateJob, clearCompleted };
}
