// Notification alert types

export interface NotificationAlert {
    id: string;
    date: string; // Format: YYYY-MM-DD
    venueId?: string;
    venueName?: string; // "Todas" if no specific venue
    enabled: boolean;
    createdAt: string;
}

export interface AlertsState {
    alerts: NotificationAlert[];
    isLoading: boolean;
}
