import { ReactNode } from "react";

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const Logo = ({ size = 30 }: { size?: number }) => (
  <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden="true" className="logo">
    <rect width="32" height="32" rx="9" fill="#064E3B" />
    <circle cx="11" cy="13" r="3.2" fill="#D6A84F" />
    <circle cx="21" cy="13" r="3.2" fill="#0D9488" />
    <circle cx="16" cy="21" r="3.2" fill="#F8FAF7" />
    <path d="M11 13L21 13L16 21Z" fill="none" stroke="#F8FAF7" strokeWidth="1.2" opacity="0.55" />
  </svg>
);

export const HomeIcon = () => (
  <Icon>
    <path d="M4 11l8-6 8 6" />
    <path d="M6 10v9h12v-9" />
  </Icon>
);
export const CoinsIcon = () => (
  <Icon>
    <ellipse cx="9" cy="7" rx="5" ry="2.5" />
    <path d="M4 7v4c0 1.4 2.2 2.5 5 2.5s5-1.1 5-2.5V7" />
    <path d="M10 15.5c.9 1.2 3 2 5 2 2.8 0 5-1.1 5-2.5v-4c0-1.4-2.2-2.5-5-2.5" />
  </Icon>
);
export const UsersIcon = () => (
  <Icon>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M3 19c.5-3.4 3-5 6-5s5.5 1.6 6 5" />
    <path d="M16 4.5a3.5 3.5 0 0 1 0 7" />
    <path d="M18 14.5c1.6.6 2.7 2.1 3 4.5" />
  </Icon>
);
export const ScaleIcon = () => (
  <Icon>
    <path d="M12 4v16" />
    <path d="M7 20h10" />
    <path d="M5 8h14" />
    <path d="M5 8l-2.5 6a3 3 0 0 0 5 0z" />
    <path d="M19 8l-2.5 6a3 3 0 0 0 5 0z" />
  </Icon>
);
export const FileIcon = () => (
  <Icon>
    <path d="M7 3h7l5 5v13H7z" />
    <path d="M14 3v5h5" />
    <path d="M10 13h6" />
    <path d="M10 17h6" />
  </Icon>
);
export const ShieldIcon = () => (
  <Icon>
    <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z" />
    <path d="M9 12l2 2 4-4" />
  </Icon>
);
export const CogIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="3" />
    <path d="M19 12a7 7 0 0 0-.1-1.3l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2.3-1.3L14 3h-4l-.3 2.4a7 7 0 0 0-2.3 1.3l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.6l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2.3 1.3L10 21h4l.3-2.4a7 7 0 0 0 2.3-1.3l2.3.9 2-3.4-2-1.5c.1-.4.1-.9.1-1.3z" />
  </Icon>
);
export const PlusIcon = () => (
  <Icon>
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </Icon>
);
export const PhoneIcon = () => (
  <Icon>
    <rect x="7" y="3" width="10" height="18" rx="2" />
    <path d="M11 18h2" />
  </Icon>
);
export const DownloadIcon = () => (
  <Icon>
    <path d="M12 4v11" />
    <path d="M7 11l5 5 5-5" />
    <path d="M5 20h14" />
  </Icon>
);
export const CheckIcon = () => (
  <Icon>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Icon>
);
export const CloseIcon = () => (
  <Icon>
    <path d="M6 6l12 12" />
    <path d="M18 6L6 18" />
  </Icon>
);
export const LogoutIcon = () => (
  <Icon>
    <path d="M10 5H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h4" />
    <path d="M15 8l4 4-4 4" />
    <path d="M19 12H10" />
  </Icon>
);
export const SearchIcon = () => (
  <Icon>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M20 20l-4-4" />
  </Icon>
);
export const RefreshIcon = () => (
  <Icon>
    <path d="M20 11a8 8 0 0 0-14.5-4.5L4 8" />
    <path d="M4 4v4h4" />
    <path d="M4 13a8 8 0 0 0 14.5 4.5L20 16" />
    <path d="M20 20v-4h-4" />
  </Icon>
);
export const MailIcon = () => (
  <Icon>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 7l9 6 9-6" />
  </Icon>
);
export const ChevronIcon = () => (
  <Icon>
    <path d="M6 9l6 6 6-6" />
  </Icon>
);
export const MenuIcon = () => (
  <Icon>
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
  </Icon>
);
