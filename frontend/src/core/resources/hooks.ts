import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listResourceNotifications,
  markAllResourceNotificationsRead,
  markResourceNotificationRead,
  type ResourceNotificationsResponse,
} from "./api";

export const resourceNotificationsQueryKey = [
  "resources",
  "notifications",
] as const;

export function useResourceNotifications() {
  return useQuery<ResourceNotificationsResponse>({
    queryKey: resourceNotificationsQueryKey,
    queryFn: () => listResourceNotifications({ limit: 50 }),
    refetchInterval: 60_000,
  });
}

export function useMarkResourceNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: string) =>
      markResourceNotificationRead(notificationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: resourceNotificationsQueryKey,
      });
    },
  });
}

export function useMarkAllResourceNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => markAllResourceNotificationsRead(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: resourceNotificationsQueryKey,
      });
    },
  });
}
