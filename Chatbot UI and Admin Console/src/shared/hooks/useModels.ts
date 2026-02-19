import { useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchModels } from '../api/admin';

export function useAvailableModels(
    provider: string,
    currentModel: string,
    onModelChange: (newModelId: string) => void
) {
    // Fetch categorized models from the backend
    const { data: modelCategories = [], isLoading } = useQuery({
        queryKey: ['models'],
        queryFn: fetchModels,
        staleTime: 300000, // Cache for 5 minutes
    });

    // Extract models based ONLY on selected provider
    const availableModels = useMemo(() => {
        if (!modelCategories.length) return [];
        const category = modelCategories.find((c) => c.name === provider);
        return category?.models || [];
    }, [modelCategories, provider]);

    // Auto-select first model if provider changes and current model isn't valid
    useEffect(() => {
        if (availableModels.length > 0) {
            const isValid = availableModels.some((m) => m.id === currentModel);
            if (!isValid) {
                onModelChange(availableModels[0].id);
            }
        }
    }, [provider, availableModels, currentModel, onModelChange]);

    return { modelCategories, availableModels, isLoading };
}