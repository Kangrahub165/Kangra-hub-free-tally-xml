'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Activity, 
  Search, 
  RefreshCw, 
  Filter, 
  Calendar, 
  User, 
  ShieldCheck, 
  AlertCircle,
  Clock,
  ArrowRight,
  Download
} from 'lucide-react';
import { getAdminActivityLogs, UserActivityLog } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';

export default function AdminActivityLogsPage() {
  const [logs, setLogs] = useState<UserActivityLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchEmail, setSearchEmail] = useState('');
  const [selectedModule, setSelectedModule] = useState('ALL');
  const [selectedStatus, setSelectedStatus] = useState('ALL');

  const fetchLogs = async () => {
    try {
      const res = await getAdminActivityLogs({
        user_id: searchEmail.trim() || undefined,
        module: selectedModule !== 'ALL' ? selectedModule : undefined,
        status: selectedStatus !== 'ALL' ? selectedStatus : undefined,
        limit: 100,
      });
      setLogs(res.logs || []);
    } catch (err) {
      console.error('Failed to load activity logs:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [selectedModule, selectedStatus]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    fetchLogs();
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchLogs();
  };

  // Filter in-memory for instant feedback when typing
  const filteredLogs = logs.filter((log) => {
    if (!searchEmail) return true;
    const term = searchEmail.toLowerCase();
    return (
      (log.user_email && log.user_email.toLowerCase().includes(term)) ||
      (log.action && log.action.toLowerCase().includes(term)) ||
      (log.user_id && log.user_id.toLowerCase().includes(term))
    );
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-fadeIn">
      
      {/* Top Header Card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              User Activity Audit Logs
            </h1>
            <Badge variant="purple" size="sm">
              PRD Audit Trail
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Immutable log recording WHO did WHAT, WHEN, in WHICH MODULE, with WHAT STATUS across Web & PWA
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-xs font-semibold flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh Logs</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4 shadow-subtle border-slate-200/80">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row items-center gap-3">
          
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by user email, action, or user ID..."
              value={searchEmail}
              onChange={(e) => setSearchEmail(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
            />
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <select
              value={selectedModule}
              onChange={(e) => setSelectedModule(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="ALL">All Modules</option>
              <option value="Sales & Purchase">Sales & Purchase</option>
              <option value="INVOICES">Invoices OCR</option>
              <option value="USER_PROFILE">User Profile</option>
              <option value="REVIEWS">Ratings & Reviews</option>
              <option value="AUTH">Authentication</option>
            </select>

            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="ALL">All Statuses</option>
              <option value="SUCCESS">Success Only</option>
              <option value="FAILED">Failed Only</option>
            </select>

            <Button type="submit" variant="primary" size="sm" className="font-bold text-xs">
              Filter
            </Button>
          </div>

        </form>
      </Card>

      {/* Audit Log Table Card */}
      <Card className="shadow-elevated overflow-hidden border-slate-200/80">
        <CardHeader className="bg-slate-50/50 border-b border-slate-100 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base">Audit Trail Records ({filteredLogs.length})</CardTitle>
            <CardDescription>Chronological events logged in server-side database</CardDescription>
          </div>
          <Badge variant="neutral" size="sm">
            WAL Mode SQLite + Supabase
          </Badge>
        </CardHeader>

        {loading ? (
          <div className="p-10 space-y-4">
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-10 w-full rounded-xl" />
          </div>
        ) : filteredLogs.length === 0 ? (
          <EmptyState
            icon={<Activity className="w-8 h-8 text-brand-400" />}
            title="No activity logs found"
            description="No actions match your current search query or module filters."
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader className="bg-slate-50/50">
                <TableRow>
                  <TableHead className="w-[180px]">Timestamp (IST)</TableHead>
                  <TableHead>User / Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Module</TableHead>
                  <TableHead className="text-center">Status</TableHead>
                  <TableHead>Details / Metadata</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.map((log) => (
                  <TableRow key={log.id} className="hover:bg-slate-50/80 transition-colors text-xs">
                    <TableCell className="font-mono text-slate-500">
                      {new Date(log.created_at).toLocaleString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: true
                      })}
                    </TableCell>
                    <TableCell>
                      <div className="font-medium text-slate-900 font-mono">
                        {log.user_email || 'Anonymous'}
                      </div>
                      {log.user_id && (
                        <div className="text-[10px] text-slate-400 font-mono truncate max-w-[140px]" title={log.user_id}>
                          {log.user_id}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-md font-mono">
                        {log.action}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant="primary" size="sm">
                        {log.module || 'Platform'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant={log.status === 'SUCCESS' ? 'success' : 'danger'} size="sm">
                        {log.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[280px]">
                      {log.metadata ? (
                        <div className="font-mono text-[11px] text-slate-600 bg-slate-100 p-1.5 rounded-lg truncate" title={JSON.stringify(log.metadata)}>
                          {typeof log.metadata === 'object' ? JSON.stringify(log.metadata) : String(log.metadata)}
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

    </div>
  );
}
