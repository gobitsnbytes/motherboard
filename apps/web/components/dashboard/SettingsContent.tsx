"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Badge,
} from "@bnb/ui";

export function SettingsContent() {
  return (
    <div className="space-y-6">
      {/* Top Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Organization */}
        <Card>
          <CardHeader>
            <CardTitle>Organization Settings</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Organization
              </span>
              <span>bits&bytes™</span>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Region
              </span>
              <span>India</span>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Status
              </span>
              <Badge>Active</Badge>
            </div>
          </CardContent>
        </Card>

        {/* Discord */}
        <Card>
          <CardHeader>
            <CardTitle>Discord Integration</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Guild Status
              </span>
              <Badge variant="success">
                Connected
              </Badge>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Bot Status
              </span>
              <Badge variant="success">
                Online
              </Badge>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Last Sync
              </span>
              <span>2 hours ago</span>
            </div>

            <Button className="w-full" disabled>
              Run Manual Sync
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Middle Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Security */}
        <Card>
          <CardHeader>
            <CardTitle>Security & Access</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span>IAM Groups</span>
              <span>--</span>
            </div>

            <div className="flex justify-between">
              <span>Permissions</span>
              <span>--</span>
            </div>

            <div className="flex justify-between">
              <span>Role Mappings</span>
              <span>--</span>
            </div>

            <div className="flex gap-3 pt-2">
              <Button asChild>
                <a href="/dashboard/iam">
                  Open IAM
                </a>
              </Button>

              <Button asChild>
                <a href="/dashboard/audit">
                  Audit Log
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* System */}
        <Card>
          <CardHeader>
            <CardTitle>System Information</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span>Version</span>
              <span>0.1.1</span>
            </div>

            <div className="flex justify-between">
              <span>Environment</span>
              <Badge variant="warning">
                Development
              </Badge>
            </div>

            <div className="flex justify-between">
              <span>API</span>
              <Badge variant="success">
                Online
              </Badge>
            </div>

            <div className="flex justify-between">
              <span>Database</span>
              <Badge variant="success">
                Healthy
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Danger Zone */}
      <Card>
        <CardHeader>
          <CardTitle>Danger Zone</CardTitle>
        </CardHeader>

        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            These actions require elevated permissions and are disabled in MVP mode.
          </p>

          <div className="flex flex-wrap gap-3">
            <Button disabled>
              Reset Cache
            </Button>

            <Button disabled>
              Rebuild Permissions
            </Button>

            <Button disabled>
              Clear Sync State
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}