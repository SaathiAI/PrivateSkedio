/**
 * Extract display initials from a user object.
 * Returns up to 2 uppercase characters.
 */
export function getProfileInitials(user) {
  const label = (
    user?.user_metadata?.full_name
    || user?.user_metadata?.name
    || user?.email
    || "User"
  );

  return label
    .split("@")[0]
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase())
    .join("") || "U";
}

/**
 * Get the display name for a user.
 */
export function getProfileLabel(user) {
  return (
    user?.user_metadata?.full_name
    || user?.user_metadata?.name
    || user?.email
    || "User"
  );
}
