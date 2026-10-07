'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Star, 
  Check, 
  EyeOff, 
  Trash2, 
  Flag, 
  RefreshCw, 
  AlertCircle,
  MessageSquare,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  User
} from 'lucide-react';
import { getAdminReviews, moderateReview, ReviewItem } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';

export default function AdminReviewsPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [moderatingId, setModeratingId] = useState<string | null>(null);

  const fetchReviews = async () => {
    try {
      const res = await getAdminReviews(filterStatus !== 'ALL' ? filterStatus : undefined);
      setReviews(res.reviews || []);
    } catch (err) {
      console.error('Failed to load reviews:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, [filterStatus]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchReviews();
  };

  const handleModerate = async (reviewId: string, newStatus: string) => {
    setModeratingId(reviewId);
    setActionSuccess(null);
    setActionError(null);
    try {
      const res = await moderateReview(reviewId, newStatus);
      if (res.success) {
        setActionSuccess(`Review marked as ${newStatus}.`);
        fetchReviews();
        setTimeout(() => setActionSuccess(null), 4000);
      }
    } catch (err: any) {
      setActionError(err?.message || 'Failed to update review status.');
      setTimeout(() => setActionError(null), 4000);
    } finally {
      setModeratingId(null);
    }
  };

  const totalReviews = reviews.length;
  const avgRating = totalReviews > 0 ? (reviews.reduce((acc, r) => acc + r.rating, 0) / totalReviews).toFixed(1) : '5.0';
  const fiveStars = reviews.filter((r) => r.rating === 5).length;
  const approvedCount = reviews.filter((r) => r.moderation_status === 'APPROVED').length;
  const pendingCount = reviews.filter((r) => r.moderation_status === 'PENDING').length;

  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-fadeIn">
      
      {/* Top Header Card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Ratings & Reviews Moderation
            </h1>
            <Badge variant="purple" size="sm">
              PRD Customer Feedback
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Moderate submitted customer reviews (1 to 5 stars), approve authentic feedback, or hide policy violations
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
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        <Card className="p-5 flex flex-col justify-between shadow-card">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Average Rating</span>
          <div className="text-2xl font-black text-amber-500 mt-2 flex items-baseline gap-1">
            <span>{avgRating}</span>
            <span className="text-base font-bold text-amber-400">★</span>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            Across {totalReviews} total customer ratings
          </div>
        </Card>

        <Card className="p-5 flex flex-col justify-between shadow-card">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">5-Star Ratings</span>
          <div className="text-2xl font-black text-slate-900 mt-2">
            {fiveStars}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-emerald-600 font-semibold">
            {totalReviews > 0 ? Math.round((fiveStars / totalReviews) * 100) : 100}% positive sentiment
          </div>
        </Card>

        <Card className="p-5 flex flex-col justify-between shadow-card">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Approved Reviews</span>
          <div className="text-2xl font-black text-emerald-600 mt-2">
            {approvedCount}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            Live on public website
          </div>
        </Card>

        <Card className="p-5 flex flex-col justify-between shadow-card">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Pending / Flagged</span>
          <div className="text-2xl font-black text-purple-600 mt-2">
            {pendingCount}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            Awaiting administrator review
          </div>
        </Card>

      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        {['ALL', 'APPROVED', 'PENDING', 'HIDDEN'].map((status) => (
          <button
            key={status}
            onClick={() => setFilterStatus(status)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              filterStatus === status
                ? 'bg-brand-600 text-white shadow-xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            {status === 'ALL' ? 'All Reviews' : status}
          </button>
        ))}
      </div>

      {/* Reviews Table */}
      <Card className="shadow-elevated overflow-hidden border-slate-200/80">
        {loading ? (
          <div className="p-8 space-y-4">
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-10 w-full rounded-xl" />
          </div>
        ) : reviews.length === 0 ? (
          <EmptyState
            icon={<MessageSquare className="w-8 h-8 text-brand-400" />}
            title="No reviews found"
            description="There are no reviews matching the selected filter."
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader className="bg-slate-50/50">
                <TableRow>
                  <TableHead className="w-[140px]">Date</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead className="w-[120px]">Rating</TableHead>
                  <TableHead>Review Comment</TableHead>
                  <TableHead className="text-center">Status</TableHead>
                  <TableHead className="text-right">Moderation Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviews.map((rev) => (
                  <TableRow key={rev.id} className="hover:bg-slate-50/80 transition-colors text-xs">
                    <TableCell className="font-mono text-slate-500">
                      {new Date(rev.created_at).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric'
                      })}
                    </TableCell>
                    <TableCell>
                      <div className="font-bold text-slate-900">{rev.user_name || 'Verified User'}</div>
                      <div className="font-mono text-[11px] text-slate-500">{rev.user_email || rev.masked_email}</div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 font-bold text-amber-500">
                        <span>{rev.rating}</span>
                        <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[320px]">
                      {rev.review_text ? (
                        <p className="text-slate-700 leading-relaxed font-normal">{rev.review_text}</p>
                      ) : (
                        <span className="text-slate-400 italic">No comment provided</span>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant={
                          rev.moderation_status === 'APPROVED'
                            ? 'success'
                            : rev.moderation_status === 'HIDDEN'
                            ? 'neutral'
                            : 'warning'
                        }
                        size="sm"
                      >
                        {rev.moderation_status || 'APPROVED'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {rev.moderation_status !== 'APPROVED' && (
                          <button
                            onClick={() => handleModerate(rev.id, 'APPROVED')}
                            disabled={moderatingId === rev.id}
                            title="Approve review"
                            className="p-1.5 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {rev.moderation_status !== 'HIDDEN' && (
                          <button
                            onClick={() => handleModerate(rev.id, 'HIDDEN')}
                            disabled={moderatingId === rev.id}
                            title="Hide from public"
                            className="p-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
                          >
                            <EyeOff className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {rev.moderation_status !== 'FLAGGED' && (
                          <button
                            onClick={() => handleModerate(rev.id, 'FLAGGED')}
                            disabled={moderatingId === rev.id}
                            title="Flag as inappropriate"
                            className="p-1.5 rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors"
                          >
                            <Flag className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => handleModerate(rev.id, 'DELETED')}
                          disabled={moderatingId === rev.id}
                          title="Delete review"
                          className="p-1.5 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
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
