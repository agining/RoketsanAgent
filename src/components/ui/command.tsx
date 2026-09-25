import { Command as CommandPrimitive } from 'cmdk';
import { Search } from 'lucide-react';
import type { ComponentProps } from 'react';
import { cn } from '../../lib/utils';
// shadcn Command composition, styled to the workspace theme.
export function Command({ className, ...props }: ComponentProps<typeof CommandPrimitive>) { return <CommandPrimitive className={cn('command-root', className)} {...props} />; }
export function CommandInput(props: ComponentProps<typeof CommandPrimitive.Input>) { return <div className="command-search"><Search size={17} /><CommandPrimitive.Input {...props} /></div>; }
export const CommandList = CommandPrimitive.List;
export const CommandEmpty = CommandPrimitive.Empty;
export const CommandGroup = CommandPrimitive.Group;
export const CommandItem = CommandPrimitive.Item;
