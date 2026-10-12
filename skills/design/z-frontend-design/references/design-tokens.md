# App Sizing
| CSS Variable     | Purpose                                        | Shadcn Components That Use It                                        | Tailwind Usage                                                                                                                                                                                                                                                                                                                                                                          | Source   |
| ---------------- | ---------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `--radius`       | Corner radius base size                        | Cards, inputs, buttons, popovers, and the derived `radius-*` tokens. | shadcn defines incremental calculations:<br><br>`--radius-sm: calc(var(--radius) * 0.6);`<br>`--radius-md: calc(var(--radius) * 0.8);`<br>`--radius-lg: var(--radius);`<br>`--radius-xl: calc(var(--radius) * 1.4);`<br>`--radius-2xl: calc(var(--radius) * 1.8);`<br>`--radius-3xl: calc(var(--radius) * 2.2);`<br>`--radius-4xl: calc(var(--radius) * 2.6);`<br><br>Use: `rounded-md` | shadcn   |
| `--base-spacing` | Base unit tailwind derives spacing values from |                                                                      | var: `--spacing: var(--base-spacing)`                                                                                                                                                                                                                                                                                                                                                   | Tailwind |

# App Colors

| CSS Variable             | Purpose                                                | Shadcn Components That Use It                                       | Tailwind Usage                                                          | Source |
| ------------------------ | ------------------------------------------------------ | ------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------ |
| `--background`           | The default app background.                            | The page shell and page sections.                                   | var: `--color-background`<br>use: `bg-background`                       | shadcn |
| `--foreground`           | The default text color, contrasting `--background`.    | Default body text.                                                  | var: `--color-foreground`<br>use: `text-foreground`                     | shadcn |
| `--primary`              | High-emphasis actions and brand surfaces.              | Default Button, selected states, badges, active accents.            | var: `--color-primary`<br>use: `bg-primary`                             | shadcn |
| `--primary-foreground`   | Text color contrasting `--primary`.                    | Labels inside primary buttons and badges.                           | var: `--color-primary-foreground`<br>use: `text-primary-foreground`     | shadcn |
| `--secondary`            | Lower-emphasis filled actions and supporting surfaces. | Secondary buttons, secondary badges, supporting UI.                 | var: `--color-secondary`<br>use: `bg-secondary`                         | shadcn |
| `--secondary-foreground` | Text color contrasting `--secondary`.                  | Labels inside secondary buttons and badges.                         | var: `--color-secondary-foreground`<br>use: `text-secondary-foreground` | shadcn |
| `--muted`                | Subtle, low-emphasis surfaces.                         | Empty states, disabled elements, subdued panels.                    | var: `--color-muted`<br>use: `bg-muted`                                 | shadcn |
| `--muted-foreground`     | Lower-emphasis content.                                | Descriptions, placeholders, helper text.                            | var: `--color-muted-foreground`<br>use: `text-muted-foreground`         | shadcn |
| `--accent`               | Interactive hover, focus, and active surfaces.         | Ghost buttons, menu highlight states, hovered rows, selected items. | var: `--color-accent`<br>use: `bg-accent`                               | shadcn |
| `--accent-foreground`    | Text color contrasting `--accent`.                     | Labels on hovered or selected items.                                | var: `--color-accent-foreground`<br>use: `text-accent-foreground`       | shadcn |
| `--destructive`          | Destructive actions and error emphasis.                | Destructive buttons, invalid states, destructive menu items.        | var: `--color-destructive`<br>use: `bg-destructive`                     | shadcn |
| `--border`               | Default borders and separators.                        | Cards, menus, tables, separators, layout dividers.                  | var: `--color-border`<br>use: `border-border`                           | shadcn |
| `--input`                | Form control borders and input surface treatment.      | Input, Textarea, Select, outline-style controls.                    | var: `--color-input`<br>use: `border-input`                             | shadcn |
| `--ring`                 | Focus rings and outlines.                              | Buttons, inputs, checkboxes, menus, other focusable controls.       | var: `--color-ring`<br>use: `ring-ring`                                 | shadcn |

# Component Specific Colors

## Cards

| CSS Variable        | Purpose                          | Shadcn Components That Use It            | Tailwind Usage                                                | Source |
| ------------------- | -------------------------------- | ---------------------------------------- | ------------------------------------------------------------- | ------ |
| `--card`            | Elevated surfaces.               | Card, dashboard panels, settings panels. | var: `--color-card`<br>use: `bg-card`                         | shadcn |
| `--card-foreground` | Text color contrasting `--card`. | Content inside cards and panels.         | var: `--color-card-foreground`<br>use: `text-card-foreground` | shadcn |

## Popovers

| CSS Variable           | Purpose                             | Shadcn Components That Use It                       | Tailwind Usage                                                      | Source |
| ---------------------- | ----------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------- | ------ |
| `--popover`            | Floating surfaces.                  | Popover, DropdownMenu, ContextMenu, other overlays. | var: `--color-popover`<br>use: `bg-popover`                         | shadcn |
| `--popover-foreground` | Text color contrasting `--popover`. | Content inside overlays.                            | var: `--color-popover-foreground`<br>use: `text-popover-foreground` | shadcn |

## Sidebar

| CSS Variable                   | Purpose                                       | Shadcn Components That Use It                              | Tailwind Usage                                                                      | Source |
| ------------------------------ | --------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------ |
| `--sidebar`                    | The base sidebar surface.                     | The Sidebar container.                                     | var: `--color-sidebar`<br>use: `bg-sidebar`                                         | shadcn |
| `--sidebar-foreground`         | Default sidebar text color.                   | Default content inside the sidebar.                        | var: `--color-sidebar-foreground`<br>use: `text-sidebar-foreground`                 | shadcn |
| `--sidebar-primary`            | High-emphasis actions inside the sidebar.     | Active items, icon tiles, badges, sidebar calls to action. | var: `--color-sidebar-primary`<br>use: `bg-sidebar-primary`                         | shadcn |
| `--sidebar-primary-foreground` | Text color contrasting `--sidebar-primary`.   | Labels on active sidebar items and badges.                 | var: `--color-sidebar-primary-foreground`<br>use: `text-sidebar-primary-foreground` | shadcn |
| `--sidebar-accent`             | Hover and selected states inside the sidebar. | Sidebar menu hover states, open items, interactive rows.   | var: `--color-sidebar-accent`<br>use: `bg-sidebar-accent`                           | shadcn |
| `--sidebar-accent-foreground`  | Text color contrasting `--sidebar-accent`.    | Labels on hovered or open sidebar rows.                    | var: `--color-sidebar-accent-foreground`<br>use: `text-sidebar-accent-foreground`   | shadcn |
| `--sidebar-border`             | Sidebar-specific borders and separators.      | Sidebar headers, groups, internal dividers.                | var: `--color-sidebar-border`<br>use: `border-sidebar-border`                       | shadcn |
| `--sidebar-ring`               | Sidebar-specific focus rings.                 | Focused controls inside the sidebar.                       | var: `--color-sidebar-ring`<br>use: `ring-sidebar-ring`                             | shadcn |
