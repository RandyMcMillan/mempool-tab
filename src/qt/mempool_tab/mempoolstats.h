// Copyright (c) 2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_QT_MEMPOOLSTATS_H
#define BITCOIN_QT_MEMPOOLSTATS_H

#include <QEvent>
#include <QWidget>
#include <QGraphicsItem>
#include <QGraphicsRectItem>
#include <QGraphicsScene>
#include <QGraphicsSimpleTextItem>
#include <QGraphicsView>

#include <policy/fees.h>
#include <qt/mempool_tab/mempooldetail.h>

class ClickableTextItem : public QObject, public QGraphicsSimpleTextItem
{
    Q_OBJECT
protected:
    void mousePressEvent(QGraphicsSceneMouseEvent *event) override;
Q_SIGNALS:
    void objectClicked(QGraphicsItem*);
};

class ClickableRectItem : public QObject, public QGraphicsRectItem
{
    Q_OBJECT
protected:
    void mousePressEvent(QGraphicsSceneMouseEvent *event) override;
Q_SIGNALS:
    void objectClicked(QGraphicsItem*);
};


class MempoolStats : public QWidget
{
    Q_OBJECT

public:
    explicit MempoolStats(QWidget *parent = Q_NULLPTR);
    void setClientModel(ClientModel *model);

public Q_SLOTS:
    void drawChart();
    void drawDetailView(
    qreal detail_x,
    qreal detail_y
    );
    int detailX();
    int detailY();
    int detailWidth();
    int detailHeight();

    void drawHorzLines(
    qreal x_increment,
    QPointF current_x_bottom,
    const int amount_of_h_lines,
    qreal maxheight_g,
    qreal maxwidth,
    qreal bottom,
    size_t max_txcount_graph,
    QFont LABELFONT
    );

    void mousePressEvent(QMouseEvent        *event) override;
    void mouseReleaseEvent(QMouseEvent      *event) override;
    void mouseDoubleClickEvent(QMouseEvent  *event) override;
    void mouseMoveEvent(QMouseEvent         *event) override;

    void showFeeRects (QEvent *event);
    void showFeeRanges(QEvent *event);

    void hideFeeRects (QEvent *event);
    void hideFeeRanges(QEvent *event);

Q_SIGNALS:
    void objectClicked(QWidget*);

private:
    ClientModel* m_clientmodel = Q_NULLPTR;

    QGraphicsView  *m_gfx_view;
    MempoolDetail  *m_detail_view;
    QGraphicsScene *m_scene;

    virtual void enterEvent(QEvent           *event) override;
    virtual void leaveEvent(QEvent           *event) override;
    virtual void resizeEvent(QResizeEvent*    event) override;
    virtual void showEvent(QShowEvent*        event) override;

    int m_selected_range = -1;
    QPoint mPoint;
    QColor pen_color;
    QColor brush_color;
    QFont gridFont;

};

#endif // BITCOIN_QT_MEMPOOLSTATS_H
